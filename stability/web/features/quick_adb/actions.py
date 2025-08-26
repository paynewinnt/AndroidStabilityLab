from __future__ import annotations

from pathlib import Path
from time import time
from typing import Any, Mapping

from stability.infrastructure.command_runner import ADBCommandRunner

from .catalog import quick_adb_command_by_id


class QuickAdbActionsMixin:
    @staticmethod
    def _quick_adb_device_ids(form: Mapping[str, list[str]]) -> list[str | None]:
        raw_values: list[str] = []
        raw_values.extend(str(item) for item in form.get("device_ids", []) or [])
        raw_values.extend(str(item) for item in form.get("device_id", []) or [])
        devices: list[str] = []
        seen: set[str] = set()
        for raw in raw_values:
            for item in raw.replace("\n", ",").replace(" ", ",").split(","):
                device_id = item.strip()
                if device_id and device_id not in seen:
                    devices.append(device_id)
                    seen.add(device_id)
        return devices or [None]

    def _handle_quick_adb_execute(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        del request_context
        form = dict(payload)
        command_id = self._required_form_value(form, "command_id")
        command = quick_adb_command_by_id(command_id)
        if command is None:
            raise ValueError(f"Unknown quick adb command: {command_id}")

        package_name = self._form_value(form, "package_name")
        if "package" in command.params and not package_name:
            raise ValueError("Missing form parameter: package_name")

        timeout_seconds = self._form_int(form, "timeout_seconds", default=command.timeout_seconds)
        timeout_seconds = min(max(timeout_seconds, 3), max(command.timeout_seconds, 180))
        executions = [
            self._execute_quick_adb_command(
                command=command,
                device_id=device_id,
                package_name=package_name,
                timeout_seconds=timeout_seconds,
            )
            for device_id in self._quick_adb_device_ids(form)
        ]
        all_ok = all(bool(item.get("result", {}).get("ok", False)) for item in executions)
        stdout = "\n\n".join(
            self._labeled_quick_adb_output(item, stream="stdout")
            for item in executions
            if str(item.get("result", {}).get("stdout", "") or "")
        )
        stderr = "\n\n".join(
            self._labeled_quick_adb_output(item, stream="stderr")
            for item in executions
            if str(item.get("result", {}).get("stderr", "") or "")
        )
        first_command = dict(executions[0].get("command", {}) or {}) if executions else {}
        return {
            "command": {
                "command_id": command.command_id,
                "title": command.title,
                "layer": command.layer,
                "group": command.group,
                "args": first_command.get("args", []),
                "full_command": first_command.get("full_command", []),
                "device_id": first_command.get("device_id", ""),
                "device_ids": [str(item.get("command", {}).get("device_id", "") or "adb-default") for item in executions],
                "timeout_seconds": timeout_seconds,
                "duration_ms": sum(int(item.get("command", {}).get("duration_ms", 0) or 0) for item in executions),
                "output_path": first_command.get("output_path", ""),
            },
            "result": {
                "ok": all_ok,
                "returncode": 0 if all_ok else 1,
                "timed_out": any(bool(item.get("result", {}).get("timed_out", False)) for item in executions),
                "stdout": stdout,
                "stderr": stderr,
            },
            "executions": executions,
        }

    def _execute_quick_adb_command(
        self,
        *,
        command: Any,
        device_id: str | None,
        package_name: str,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        artifact_dir = Path("runtime/quick_adb")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        if "bugreport_path" in command.params:
            device_part = str(device_id or "default").replace("/", "_").replace(":", "_")
            artifact_dir = artifact_dir / f"{int(time())}_{device_part}"
            artifact_dir.mkdir(parents=True, exist_ok=True)

        args = command.render_args(package_name=package_name, artifact_dir=artifact_dir)
        runner = ADBCommandRunner(device_id=device_id)
        started_at = time()
        result = runner.run_adb(args, timeout_seconds=timeout_seconds)
        duration_ms = int((time() - started_at) * 1000)
        output_path = str(artifact_dir / "bugreport.zip") if "bugreport_path" in command.params else ""
        return {
            "command": {
                "args": list(args),
                "full_command": runner.build_adb_command(args),
                "device_id": device_id or "",
                "timeout_seconds": timeout_seconds,
                "duration_ms": duration_ms,
                "output_path": output_path,
            },
            "result": {
                "ok": result.ok,
                "returncode": result.returncode,
                "timed_out": result.timed_out,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
        }

    @staticmethod
    def _labeled_quick_adb_output(execution: Mapping[str, Any], *, stream: str) -> str:
        command = dict(execution.get("command", {}) or {})
        result = dict(execution.get("result", {}) or {})
        device_label = str(command.get("device_id", "") or "adb-default")
        return f"[{device_label}]\n{str(result.get(stream, '') or '')}"
