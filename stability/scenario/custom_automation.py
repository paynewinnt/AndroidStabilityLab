from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any, Callable, Mapping, Sequence

from stability.domain import TaskTemplateType
from stability.infrastructure.adb import ADBCollector
from stability.infrastructure.command_runner import CommandResult, CommandRunner, SubprocessCommandRunner
from stability.time_utils import now_beijing_string

from .base import ScenarioExecutionResult


class CustomAutomationScenarioRunner:
    """Execute business traversal through uiautomator2, adb scripts, or external callbacks."""

    def __init__(
        self,
        *,
        collector_factory=ADBCollector,
        command_runner: CommandRunner | None = None,
        sleep_func: Callable[[float], None] | None = None,
        uiautomator2_client_factory: Callable[[str], object] | None = None,
    ) -> None:
        self._collector_factory = collector_factory
        self._command_runner = command_runner or SubprocessCommandRunner()
        self._sleep = sleep_func or time.sleep
        self._uiautomator2_client_factory = uiautomator2_client_factory

    def execute(self, task, run, instance, layout, log_path: Path) -> ScenarioExecutionResult:
        if getattr(task, "template_type", None) != TaskTemplateType.CUSTOM:
            raise ValueError("CustomAutomationScenarioRunner only supports custom template tasks.")

        params = dict(getattr(task, "task_params", {}) or {})
        mode = str(params.get("automation_mode", "") or params.get("execution_mode", "") or "").strip().lower()
        if not mode:
            return ScenarioExecutionResult(
                success=False,
                note="custom 模板执行失败：缺少 automation_mode，可选 uiautomator2 / adb_script / external_script。",
                exit_reason="execution_error",
                result_level="failed",
                metadata={"template_type": TaskTemplateType.CUSTOM.value},
            )
        if mode == "uiautomator2":
            return self._execute_uiautomator2(task=task, run=run, instance=instance, layout=layout, log_path=log_path, params=params)
        if mode == "adb_script":
            return self._execute_adb_script(task=task, run=run, instance=instance, layout=layout, log_path=log_path, params=params)
        if mode == "external_script":
            return self._execute_external_script(task=task, run=run, instance=instance, layout=layout, log_path=log_path, params=params)
        return ScenarioExecutionResult(
            success=False,
            note=f"custom 模板执行失败：不支持的 automation_mode={mode}。",
            exit_reason="execution_error",
            result_level="failed",
            metadata={"template_type": TaskTemplateType.CUSTOM.value, "automation_mode": mode},
        )

    def _execute_uiautomator2(self, *, task, run, instance, layout, log_path: Path, params: Mapping[str, Any]) -> ScenarioExecutionResult:
        device_id = str(getattr(instance, "device_id", "") or "")
        package_name = str(getattr(getattr(task, "target_app", None), "package_name", "") or "")
        steps = self._automation_steps(params)
        if not device_id:
            return self._failure("uiautomator2", "缺少目标设备。")
        if not steps:
            return self._failure("uiautomator2", "缺少 automation_steps。")

        try:
            client = self._connect_uiautomator2(device_id)
        except Exception as exc:
            return self._failure(
                "uiautomator2",
                f"uiautomator2 连接失败：{exc}",
                extra={"device_id": device_id},
            )

        execution_steps: list[dict[str, Any]] = []
        artifact_paths: list[str] = []
        automation_dir = Path(layout.artifacts_dir) / "automation"
        automation_dir.mkdir(parents=True, exist_ok=True)
        scenario_name = str(params.get("scenario_name", "") or params.get("entry_name", "") or "custom_uiautomator2")
        for index, raw_step in enumerate(steps, start=1):
            step = dict(raw_step or {})
            action = str(step.get("action", "") or "").strip().lower()
            step_id = str(step.get("step_id", "") or f"step_{index}")
            started_at = now_beijing_string()
            timer_started = time.monotonic()
            step_artifacts: list[str] = []
            try:
                self._run_u2_step(
                    client=client,
                    package_name=package_name,
                    step=step,
                    automation_dir=automation_dir,
                    step_index=index,
                    step_artifacts=step_artifacts,
                )
                finished_at = now_beijing_string()
                execution_steps.append(
                    {
                        "step_id": step_id,
                        "label": str(step.get("label", "") or action or step_id),
                        "action": action,
                        "status": "passed",
                        "started_at": started_at,
                        "finished_at": finished_at,
                        "duration_ms": int((time.monotonic() - timer_started) * 1000),
                        "artifact_paths": step_artifacts,
                    }
                )
                artifact_paths.extend(step_artifacts)
            except Exception as exc:
                finished_at = now_beijing_string()
                execution_steps.append(
                    {
                        "step_id": step_id,
                        "label": str(step.get("label", "") or action or step_id),
                        "action": action,
                        "status": "failed",
                        "started_at": started_at,
                        "finished_at": finished_at,
                        "duration_ms": int((time.monotonic() - timer_started) * 1000),
                        "failure_summary": str(exc),
                        "artifact_paths": step_artifacts,
                    }
                )
                artifact_paths.extend(step_artifacts)
                self._append_log(log_path, f"[custom][uiautomator2] step={step_id} failed: {exc}")
                return ScenarioExecutionResult(
                    success=False,
                    note=f"业务遍历失败：步骤 {step_id} 执行失败。",
                    exit_reason="execution_error",
                    result_level="failed",
                    highlights=(f"failed step: {step_id}",),
                    metadata=self._automation_metadata(
                        mode="uiautomator2",
                        engine="uiautomator2",
                        scenario_name=scenario_name,
                        entry_name=str(params.get("entry_name", "") or scenario_name),
                        execution_steps=execution_steps,
                        artifact_paths=artifact_paths,
                        package_name=package_name,
                        device_id=device_id,
                    ),
                )

        return ScenarioExecutionResult(
            success=True,
            note=f"业务遍历执行完成，共完成 {len(execution_steps)} 个 uiautomator2 步骤。",
            exit_reason="completed",
            result_level="passed",
            highlights=(f"uiautomator2 steps completed: {len(execution_steps)}",),
            metadata=self._automation_metadata(
                mode="uiautomator2",
                engine="uiautomator2",
                scenario_name=scenario_name,
                entry_name=str(params.get("entry_name", "") or scenario_name),
                execution_steps=execution_steps,
                artifact_paths=artifact_paths,
                package_name=package_name,
                device_id=device_id,
            ),
        )

    def _execute_adb_script(self, *, task, run, instance, layout, log_path: Path, params: Mapping[str, Any]) -> ScenarioExecutionResult:
        device_id = str(getattr(instance, "device_id", "") or "")
        if not device_id:
            return self._failure("adb_script", "缺少目标设备。")
        commands = list(params.get("adb_commands", ()) or ())
        if not commands:
            return self._failure("adb_script", "缺少 adb_commands。")

        collector = self._collector_factory(timeout=10, retry_count=1)
        collector.device_id = device_id
        execution_steps: list[dict[str, Any]] = []
        for index, raw_step in enumerate(commands, start=1):
            if isinstance(raw_step, str):
                step = {"command": raw_step, "label": raw_step}
            else:
                step = dict(raw_step or {})
            command = str(step.get("command", "") or "").strip()
            if not command:
                return self._failure("adb_script", f"第 {index} 条 adb_commands 缺少 command。", extra={"device_id": device_id})
            started_at = now_beijing_string()
            timer_started = time.monotonic()
            result = collector._run_adb_command(command, log_errors=False)
            finished_at = now_beijing_string()
            output_text = str(result or "")
            failure_markers = ("error:", "failed", "exception", "not found")
            failed = any(marker in output_text.lower() for marker in failure_markers) and not bool(step.get("allow_failure", False))
            execution_steps.append(
                {
                    "step_id": str(step.get("step_id", "") or f"adb_step_{index}"),
                    "label": str(step.get("label", "") or command),
                    "action": "adb_command",
                    "command": command,
                    "status": "failed" if failed else "passed",
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "duration_ms": int((time.monotonic() - timer_started) * 1000),
                    "stdout_tail": self._tail_text(output_text),
                }
            )
            if failed:
                return ScenarioExecutionResult(
                    success=False,
                    note=f"adb_script 执行失败：步骤 {index} 返回错误输出。",
                    exit_reason="execution_error",
                    result_level="failed",
                    highlights=(f"failed adb step: {index}",),
                    metadata=self._automation_metadata(
                        mode="adb_script",
                        engine="adb_script",
                        scenario_name=str(params.get("scenario_name", "") or "custom_adb_script"),
                        entry_name=str(params.get("entry_name", "") or "custom_adb_script"),
                        execution_steps=execution_steps,
                        artifact_paths=[],
                        package_name=str(getattr(getattr(task, "target_app", None), "package_name", "") or ""),
                        device_id=device_id,
                    ),
                )

        return ScenarioExecutionResult(
            success=True,
            note=f"adb_script 执行完成，共完成 {len(execution_steps)} 个步骤。",
            exit_reason="completed",
            result_level="passed",
            highlights=(f"adb steps completed: {len(execution_steps)}",),
            metadata=self._automation_metadata(
                mode="adb_script",
                engine="adb_script",
                scenario_name=str(params.get("scenario_name", "") or "custom_adb_script"),
                entry_name=str(params.get("entry_name", "") or "custom_adb_script"),
                execution_steps=execution_steps,
                artifact_paths=[],
                package_name=str(getattr(getattr(task, "target_app", None), "package_name", "") or ""),
                device_id=device_id,
            ),
        )

    def _execute_external_script(self, *, task, run, instance, layout, log_path: Path, params: Mapping[str, Any]) -> ScenarioExecutionResult:
        device_id = str(getattr(instance, "device_id", "") or "")
        package_name = str(getattr(getattr(task, "target_app", None), "package_name", "") or "")
        script_path = Path(str(params.get("script_path", "") or "").strip())
        if not script_path:
            return self._failure("external_script", "缺少 script_path。")
        if not script_path.exists():
            return self._failure("external_script", f"脚本不存在：{script_path}")

        context_path = Path(layout.temp_dir) / "automation_context.json"
        output_path = Path(layout.temp_dir) / "automation_output.json"
        context_payload = {
            "task": {
                "task_id": str(getattr(task, "task_id", "") or ""),
                "task_name": str(getattr(task, "task_name", "") or ""),
                "template_type": str(getattr(getattr(task, "template_type", None), "value", getattr(task, "template_type", "")) or ""),
                "package_name": package_name,
                "task_params": dict(getattr(task, "task_params", {}) or {}),
            },
            "run": {
                "run_id": str(getattr(run, "run_id", "") or ""),
                "task_definition_id": str(getattr(run, "task_definition_id", "") or ""),
            },
            "instance": {
                "instance_id": str(getattr(instance, "instance_id", "") or ""),
                "device_id": device_id,
            },
            "runtime": {
                "root": str(layout.root),
                "artifacts_dir": str(layout.artifacts_dir),
                "temp_dir": str(layout.temp_dir),
            },
        }
        context_path.parent.mkdir(parents=True, exist_ok=True)
        context_path.write_text(json.dumps(context_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        command = self._external_script_command(script_path=script_path, params=params, context_path=context_path, output_path=output_path)
        timeout_seconds = max(int(params.get("script_timeout_seconds", 300) or 300), 1)
        started_at = now_beijing_string()
        timer_started = time.monotonic()
        result = self._command_runner.run(command, timeout_seconds=timeout_seconds)
        finished_at = now_beijing_string()
        callback_payload = self._load_external_script_output(output_path=output_path, stdout=result.stdout)
        execution_steps = [
            {
                "step_id": "external_script",
                "label": str(params.get("entry_name", "") or script_path.name),
                "action": "external_script",
                "status": "failed" if result.timed_out or result.returncode not in {0, None} else "passed",
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_ms": int((time.monotonic() - timer_started) * 1000),
                "stdout_tail": self._tail_text(result.stdout),
                "stderr_tail": self._tail_text(result.stderr),
            }
        ]
        success = not result.timed_out and result.returncode in {0, None} and bool(callback_payload.get("success", True))
        note = str(callback_payload.get("note", "") or "")
        if not note:
            note = (
                "外部自动化脚本执行完成。"
                if success
                else f"外部自动化脚本执行失败，退出码 {result.returncode}。"
            )
        return ScenarioExecutionResult(
            success=success,
            note=note,
            exit_reason="completed" if success else "execution_error",
            result_level="passed" if success else "failed",
            highlights=tuple(callback_payload.get("highlights", ()) or ()),
            metadata=self._automation_metadata(
                mode="external_script",
                engine="external_script",
                scenario_name=str(params.get("scenario_name", "") or script_path.stem),
                entry_name=str(params.get("entry_name", "") or script_path.name),
                execution_steps=execution_steps + list(callback_payload.get("steps", ()) or ()),
                artifact_paths=list(callback_payload.get("artifact_paths", ()) or ()),
                package_name=package_name,
                device_id=device_id,
                callback_summary={
                    "context_path": str(context_path),
                    "output_path": str(output_path) if output_path.exists() else "",
                    "stdout_tail": self._tail_text(result.stdout),
                    "stderr_tail": self._tail_text(result.stderr),
                    "return_code": result.returncode,
                    "timed_out": result.timed_out,
                    "callback_payload": callback_payload,
                },
            ),
        )

    def _connect_uiautomator2(self, device_id: str) -> object:
        if self._uiautomator2_client_factory is not None:
            return self._uiautomator2_client_factory(device_id)
        try:
            import uiautomator2 as u2  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on local env
            raise RuntimeError("uiautomator2 is unavailable. Install it with `pip install -U uiautomator2`.") from exc
        return u2.connect(device_id)

    def _run_u2_step(
        self,
        *,
        client: object,
        package_name: str,
        step: Mapping[str, Any],
        automation_dir: Path,
        step_index: int,
        step_artifacts: list[str],
    ) -> None:
        action = str(step.get("action", "") or "").strip().lower()
        if action in {"launch_app", "app_start"}:
            target = str(step.get("package_name", "") or package_name)
            activity = str(step.get("activity", "") or "")
            if activity and hasattr(client, "app_start"):
                client.app_start(target, activity=activity)
            elif hasattr(client, "app_start"):
                client.app_start(target)
            else:
                raise RuntimeError("uiautomator2 client does not support app_start.")
            return
        if action in {"stop_app", "app_stop"}:
            target = str(step.get("package_name", "") or package_name)
            if hasattr(client, "app_stop"):
                client.app_stop(target)
                return
            raise RuntimeError("uiautomator2 client does not support app_stop.")
        if action in {"click", "tap"}:
            client.click(float(step.get("x", 0)), float(step.get("y", 0)))
            return
        if action == "swipe":
            client.swipe(
                float(step.get("from_x", 0)),
                float(step.get("from_y", 0)),
                float(step.get("to_x", 0)),
                float(step.get("to_y", 0)),
                duration=float(step.get("duration_ms", 0) or 0) / 1000.0 if step.get("duration_ms") else None,
            )
            return
        if action == "press":
            client.press(str(step.get("key", "") or "home"))
            return
        if action in {"input_text", "set_text"}:
            text = str(step.get("text", "") or "")
            if not text:
                raise RuntimeError("input_text step requires text.")
            if hasattr(client, "send_keys"):
                client.send_keys(text, clear=bool(step.get("clear", False)))
                return
            raise RuntimeError("uiautomator2 client does not support send_keys.")
        if action == "wait":
            seconds = float(step.get("seconds", 0) or 0)
            milliseconds = int(step.get("milliseconds", 0) or 0)
            total_seconds = seconds if seconds > 0 else milliseconds / 1000.0
            if total_seconds > 0:
                self._sleep(total_seconds)
            return
        if action == "click_selector":
            selector = self._resolve_selector(client, step)
            if hasattr(selector, "click"):
                selector.click()
                return
            raise RuntimeError("selector does not support click.")
        if action == "assert_exists":
            selector = self._resolve_selector(client, step)
            exists = getattr(selector, "exists", None)
            if callable(exists):
                exists = exists()
            if not exists:
                raise RuntimeError(str(step.get("failure_summary", "") or "selector not found"))
            return
        if action == "screenshot":
            path = automation_dir / f"step_{step_index:02d}_{self._safe_name(step.get('name', '') or 'screenshot')}.png"
            if hasattr(client, "screenshot"):
                client.screenshot(str(path))
                step_artifacts.append(str(path))
                return
            raise RuntimeError("uiautomator2 client does not support screenshot.")
        if action == "dump_hierarchy":
            path = automation_dir / f"step_{step_index:02d}_{self._safe_name(step.get('name', '') or 'hierarchy')}.xml"
            if hasattr(client, "dump_hierarchy"):
                payload = client.dump_hierarchy()
                path.write_text(str(payload or ""), encoding="utf-8")
                step_artifacts.append(str(path))
                return
            raise RuntimeError("uiautomator2 client does not support dump_hierarchy.")
        raise RuntimeError(f"Unsupported uiautomator2 action: {action}")

    @staticmethod
    def _resolve_selector(client: object, step: Mapping[str, Any]) -> object:
        selector_payload = dict(step.get("selector", {}) or {})
        for key in ("text", "textContains", "resourceId", "description", "className"):
            if key in step and step.get(key):
                selector_payload[key] = step.get(key)
        xpath = str(step.get("xpath", "") or selector_payload.get("xpath", "") or "").strip()
        if xpath:
            if hasattr(client, "xpath"):
                return client.xpath(xpath)
            raise RuntimeError("uiautomator2 client does not support xpath selector.")
        if not selector_payload:
            raise RuntimeError("selector step requires selector/text/resourceId/description/xpath.")
        if callable(client):
            return client(**selector_payload)
        raise RuntimeError("uiautomator2 client does not support selector lookup.")

    @staticmethod
    def _automation_steps(params: Mapping[str, Any]) -> list[dict[str, Any]]:
        raw = params.get("automation_steps", ()) or params.get("steps", ()) or ()
        return [dict(item or {}) for item in raw if isinstance(item, Mapping)]

    @staticmethod
    def _external_script_command(*, script_path: Path, params: Mapping[str, Any], context_path: Path, output_path: Path) -> tuple[str, ...]:
        args = [str(item) for item in (params.get("script_args", ()) or ()) if str(item).strip()]
        context_arg = str(params.get("context_arg_name", "") or "--asl-context")
        output_arg = str(params.get("output_arg_name", "") or "--asl-output")
        if script_path.suffix == ".py":
            python_bin = str(params.get("python_executable", "") or "python")
            base = [python_bin, str(script_path)]
        else:
            base = [str(script_path)]
        if context_arg:
            base.extend([context_arg, str(context_path)])
        if output_arg:
            base.extend([output_arg, str(output_path)])
        base.extend(args)
        return tuple(base)

    @staticmethod
    def _load_external_script_output(*, output_path: Path, stdout: str) -> dict[str, Any]:
        payload_text = ""
        if output_path.exists():
            payload_text = output_path.read_text(encoding="utf-8").strip()
        elif str(stdout or "").strip().startswith("{"):
            payload_text = str(stdout or "").strip()
        if not payload_text:
            return {}
        try:
            parsed = json.loads(payload_text)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, Mapping) else {}

    @staticmethod
    def _automation_metadata(
        *,
        mode: str,
        engine: str,
        scenario_name: str,
        entry_name: str,
        execution_steps: Sequence[Mapping[str, Any]],
        artifact_paths: Sequence[str],
        package_name: str,
        device_id: str,
        callback_summary: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "template_type": TaskTemplateType.CUSTOM.value,
            "automation_mode": mode,
            "automation_engine": engine,
            "entry_name": entry_name,
            "scenario_name": scenario_name,
            "package_name": package_name,
            "device_id": device_id,
            "execution_steps": [dict(item) for item in execution_steps],
            "step_count": len(execution_steps),
            "artifact_paths": list(artifact_paths),
            "callback_summary": dict(callback_summary or {}),
        }

    @staticmethod
    def _failure(mode: str, note: str, extra: Mapping[str, Any] | None = None) -> ScenarioExecutionResult:
        metadata = {"template_type": TaskTemplateType.CUSTOM.value, "automation_mode": mode}
        if extra:
            metadata.update(dict(extra))
        return ScenarioExecutionResult(
            success=False,
            note=f"custom 模板执行失败：{note}",
            exit_reason="execution_error",
            result_level="failed",
            metadata=metadata,
        )

    @staticmethod
    def _tail_text(value: str, limit: int = 2000) -> str:
        text = str(value or "").strip()
        if len(text) <= limit:
            return text
        return text[-limit:]

    @staticmethod
    def _append_log(path: Path, line: str) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line.strip())
            handle.write("\n")

    @staticmethod
    def _safe_name(value: object) -> str:
        text = str(value or "").strip().replace(" ", "_")
        return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in text) or "artifact"
