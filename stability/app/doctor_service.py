from __future__ import annotations

import base64
from dataclasses import dataclass, field
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
import shutil
import socket
import sys
from typing import Any, Mapping, Sequence
import urllib.error
import urllib.request

from stability.app.integration_outbox_service import IntegrationOutboxService
from stability.domain import WebhookSubscription
from stability.infrastructure.command_runner import CommandResult, CommandRunner, SubprocessCommandRunner
from stability.infrastructure.monitoring_config import (
    DEFAULT_PERFETTO_REMOTE_PATH_TEMPLATE,
    SUPPORTED_MONITORING_BACKENDS,
    load_monitoring_profile_registry,
)
from stability.time_utils import now_beijing_string


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    summary: str
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DoctorReport:
    generated_at: str
    ok: bool
    checks: Sequence[DoctorCheck]
    summary: Mapping[str, Any] = field(default_factory=dict)


class DoctorService:
    """Cross-cutting local environment diagnostics for CLI and Web."""

    def __init__(
        self,
        *,
        runtime_root: str | Path = "runtime",
        config_dir: str | Path = "config",
        web_host: str = "127.0.0.1",
        web_port: int = 8030,
        outbox_root: str | Path = "runtime/integration_outbox",
        device_id: str = "",
        package_name: str = "",
        command_runner: CommandRunner | None = None,
        check_webhooks: bool = False,
        webhook_timeout_seconds: int = 5,
    ) -> None:
        self._runtime_root = Path(runtime_root)
        self._config_dir = Path(config_dir)
        self._web_host = str(web_host or "127.0.0.1")
        self._web_port = int(web_port or 8030)
        self._outbox_root = Path(outbox_root)
        self._device_id = str(device_id or "").strip()
        self._package_name = str(package_name or "").strip()
        self._command_runner = command_runner or SubprocessCommandRunner()
        self._check_webhooks = bool(check_webhooks)
        self._webhook_timeout_seconds = max(int(webhook_timeout_seconds), 1)

    def run(self) -> DoctorReport:
        checks = [
            self._check_python(),
            self._check_adb_available(),
            self._check_adb_devices(),
            self._check_tcp_devices(),
            self._check_runtime_permissions(),
            self._check_config_json(),
            self._check_web_port(),
            self._check_monitoring_backends(),
            self._check_outbox_webhooks(),
            self._check_feishu_webhook(),
        ]
        if self._device_id:
            checks.extend(self._target_device_checks())
        counts = {
            "ok": sum(1 for item in checks if item.status == "ok"),
            "warn": sum(1 for item in checks if item.status == "warn"),
            "fail": sum(1 for item in checks if item.status == "fail"),
            "skipped": sum(1 for item in checks if item.status == "skipped"),
        }
        return DoctorReport(
            generated_at=now_beijing_string(),
            ok=counts["fail"] == 0,
            checks=tuple(checks),
            summary={
                "total": len(checks),
                **counts,
                "runtime_root": str(self._runtime_root),
                "config_dir": str(self._config_dir),
                "web": {"host": self._web_host, "port": self._web_port},
                "target_device": {
                    "device_id": self._device_id,
                    "package_name": self._package_name,
                    "enabled": bool(self._device_id),
                },
            },
        )

    def _check_python(self) -> DoctorCheck:
        version = sys.version_info
        dependencies = self._python_dependency_status()
        missing_core = [item["package"] for item in dependencies if item["required"] and not item["available"]]
        ok = version >= (3, 10) and not missing_core
        return DoctorCheck(
            name="python",
            status="ok" if ok else "fail",
            summary=(
                "Python 版本和核心依赖满足要求。"
                if ok
                else "Python 版本过低或核心依赖缺失，建议检查虚拟环境和 requirements.txt。"
            ),
            details={
                "executable": sys.executable,
                "version": sys.version.split()[0],
                "required": ">=3.10",
                "dependencies": dependencies,
            },
        )

    def _check_adb_available(self) -> DoctorCheck:
        result = self._run(["adb", "version"], timeout_seconds=5)
        adb_path = shutil.which("adb") or ""
        return DoctorCheck(
            name="adb_available",
            status="ok" if result.ok else "fail",
            summary="ADB 可用。" if result.ok else "ADB 不可用或执行失败。",
            details={
                "adb_path": adb_path,
                "returncode": result.returncode,
                "stdout": self._tail(result.stdout),
                "stderr": self._tail(result.stderr),
                "timed_out": result.timed_out,
            },
        )

    def _check_adb_devices(self) -> DoctorCheck:
        result = self._run(["adb", "devices", "-l"], timeout_seconds=8)
        if not result.ok:
            return DoctorCheck(
                name="adb_devices",
                status="fail",
                summary="无法读取 ADB devices。",
                details=self._command_details(result),
            )
        devices = self._parse_adb_devices(result.stdout)
        counts: dict[str, int] = {}
        for device in devices:
            status = str(device.get("status", "unknown") or "unknown")
            counts[status] = counts.get(status, 0) + 1
        if not devices:
            status = "warn"
            summary = "ADB 可用，但当前没有发现设备。"
        elif counts.get("device", 0) > 0:
            status = "ok"
            summary = "ADB 已发现可用设备。"
        else:
            status = "warn"
            summary = "ADB 发现设备，但没有 device 状态的可用设备。"
        return DoctorCheck(
            name="adb_devices",
            status=status,
            summary=summary,
            details={"devices": devices, "counts": counts},
        )

    def _check_tcp_devices(self) -> DoctorCheck:
        devices_result = self._run(["adb", "devices"], timeout_seconds=8)
        devices = self._parse_adb_devices(devices_result.stdout) if devices_result.ok else []
        tcp_devices = [item for item in devices if self._split_host_port(str(item.get("serial", "") or ""))]
        if not tcp_devices:
            return DoctorCheck(
                name="tcp_devices",
                status="skipped",
                summary="当前没有 host:port 形式的 TCP ADB 设备。",
                details={},
            )
        probes = []
        reachable = 0
        for device in tcp_devices:
            serial = str(device.get("serial", "") or "")
            host_port = self._split_host_port(serial)
            if not host_port:
                continue
            host, port = host_port
            ok, error = self._probe_tcp(host, port)
            reachable += 1 if ok else 0
            probes.append({"serial": serial, "host": host, "port": port, "reachable": ok, "error": error})
        return DoctorCheck(
            name="tcp_devices",
            status="ok" if reachable == len(probes) else "warn",
            summary=f"TCP ADB 可达 {reachable}/{len(probes)}。",
            details={"probes": probes},
        )

    def _check_runtime_permissions(self) -> DoctorCheck:
        test_path = self._runtime_root / ".doctor_write_test"
        try:
            self._runtime_root.mkdir(parents=True, exist_ok=True)
            test_path.write_text("ok", encoding="utf-8")
            test_path.unlink(missing_ok=True)
            return DoctorCheck(
                name="runtime_permissions",
                status="ok",
                summary="runtime 目录可读写。",
                details={"runtime_root": str(self._runtime_root), "exists": self._runtime_root.exists()},
            )
        except OSError as exc:
            return DoctorCheck(
                name="runtime_permissions",
                status="fail",
                summary="runtime 目录不可写。",
                details={"runtime_root": str(self._runtime_root), "error": str(exc)},
            )

    def _check_config_json(self) -> DoctorCheck:
        if not self._config_dir.exists():
            return DoctorCheck(
                name="config_json",
                status="warn",
                summary="config 目录不存在，平台会使用默认配置。",
                details={"config_dir": str(self._config_dir), "files": []},
            )
        files = sorted(self._config_dir.glob("*.json"))
        invalid = []
        for path in files:
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                invalid.append({"path": str(path), "error": str(exc)})
        return DoctorCheck(
            name="config_json",
            status="fail" if invalid else "ok",
            summary="config JSON 校验通过。" if not invalid else f"发现 {len(invalid)} 个无效 config JSON。",
            details={"config_dir": str(self._config_dir), "file_count": len(files), "invalid": invalid},
        )

    def _check_web_port(self) -> DoctorCheck:
        ok, error = self._probe_tcp(self._web_host, self._web_port)
        return DoctorCheck(
            name="web_port",
            status="ok" if ok else "warn",
            summary=(
                f"Web 端口 {self._web_host}:{self._web_port} 已监听。"
                if ok
                else f"Web 端口 {self._web_host}:{self._web_port} 当前未监听。"
            ),
            details={"host": self._web_host, "port": self._web_port, "reachable": ok, "error": error},
        )

    def _check_monitoring_backends(self) -> DoctorCheck:
        solox_spec = importlib.util.find_spec("solox")
        perfetto_host = shutil.which("perfetto") or ""
        registry = load_monitoring_profile_registry(self._config_dir / "monitoring.json")
        profiles = dict(registry.get("profiles", {}) or {})
        missing_optional = []
        if solox_spec is None:
            missing_optional.append("solox")
        if not perfetto_host:
            missing_optional.append("host_perfetto_binary")
        return DoctorCheck(
            name="monitoring_backends",
            status="warn" if missing_optional else "ok",
            summary=(
                "监控 backend 基础检查通过。"
                if not missing_optional
                else "部分可选监控 backend 依赖缺失，基础 ADB 采样仍可用。"
            ),
            details={
                "supported_backends": list(SUPPORTED_MONITORING_BACKENDS),
                "configured_default_profile": str(registry.get("default_profile", "adb") or "adb"),
                "configured_profiles": sorted(profiles.keys()),
                "solox_available": solox_spec is not None,
                "perfetto_binary": perfetto_host,
                "missing_optional": missing_optional,
            },
        )

    def _check_outbox_webhooks(self) -> DoctorCheck:
        try:
            webhooks = IntegrationOutboxService(root_dir=self._outbox_root).list_webhooks()
        except Exception as exc:
            return DoctorCheck(
                name="outbox_webhooks",
                status="fail",
                summary="无法读取 outbox webhook 配置。",
                details={"outbox_root": str(self._outbox_root), "error": str(exc)},
            )
        channels: dict[str, int] = {}
        missing_secrets = []
        for webhook in webhooks:
            channel = str(webhook.delivery_channel or "generic")
            channels[channel] = channels.get(channel, 0) + 1
            if self._webhook_requires_secret(webhook) and not str(webhook.signing_secret or "").strip():
                missing_secrets.append(webhook.name)
        if not webhooks:
            status = "warn"
            summary = "当前未配置 outbox webhook。"
        elif missing_secrets:
            status = "warn"
            summary = "已配置 webhook，但部分外部 endpoint 缺少 signing_secret。"
        else:
            status = "ok"
            summary = "outbox webhook 配置可读取。"
        return DoctorCheck(
            name="outbox_webhooks",
            status=status,
            summary=summary,
            details={
                "outbox_root": str(self._outbox_root),
                "webhook_count": len(webhooks),
                "channels": channels,
                "missing_signing_secret": missing_secrets,
                "webhooks": [self._webhook_summary(item) for item in webhooks],
            },
        )

    def _check_feishu_webhook(self) -> DoctorCheck:
        try:
            webhooks = IntegrationOutboxService(root_dir=self._outbox_root).list_webhooks()
        except Exception as exc:
            return DoctorCheck(
                name="feishu_webhook",
                status="fail",
                summary="无法读取飞书 webhook 配置。",
                details={"error": str(exc)},
            )
        feishu_webhooks = [item for item in webhooks if str(item.delivery_channel or "") == "feishu_bot"]
        if not feishu_webhooks:
            return DoctorCheck(
                name="feishu_webhook",
                status="skipped",
                summary="当前未配置飞书机器人 webhook。",
                details={},
            )
        if not self._check_webhooks:
            return DoctorCheck(
                name="feishu_webhook",
                status="skipped",
                summary="已发现飞书 webhook；默认不发送诊断消息。CLI 可加 --check-webhooks 做真实连通性检查。",
                details={"webhooks": [self._webhook_summary(item) for item in feishu_webhooks]},
            )
        results = [self._post_feishu_doctor_ping(item) for item in feishu_webhooks]
        failed = [item for item in results if not item.get("ok")]
        return DoctorCheck(
            name="feishu_webhook",
            status="fail" if failed else "ok",
            summary="飞书 webhook 连通性检查通过。" if not failed else f"飞书 webhook 连通性失败 {len(failed)}/{len(results)}。",
            details={"results": results},
        )

    def _target_device_checks(self) -> list[DoctorCheck]:
        return [
            self._check_target_device_authorization(),
            self._check_target_device_shell(),
            self._check_target_package(),
            self._check_target_perfetto(),
            self._check_target_perfetto_write_permission(),
            self._check_target_wireless_reachability(),
        ]

    def _check_target_device_authorization(self) -> DoctorCheck:
        devices_result = self._run(["adb", "devices", "-l"], timeout_seconds=8)
        state_result = self._run(["adb", "-s", self._device_id, "get-state"], timeout_seconds=5)
        devices = self._parse_adb_devices(devices_result.stdout) if devices_result.ok else []
        matched = next((item for item in devices if str(item.get("serial", "")) == self._device_id), None)
        state = state_result.stdout.strip() if state_result.ok else ""
        if matched and str(matched.get("status", "")) == "device" and state == "device":
            status = "ok"
            summary = "目标设备已授权且处于 device 状态。"
        elif matched:
            status = "fail"
            summary = "目标设备已发现，但未处于可用授权状态。"
        else:
            status = "fail"
            summary = "adb devices 中未发现目标设备。"
        return DoctorCheck(
            name="target_device_authorization",
            status=status,
            summary=summary,
            details={
                "device_id": self._device_id,
                "matched_device": matched or {},
                "get_state": state,
                "get_state_result": self._command_details(state_result),
            },
        )

    def _check_target_device_shell(self) -> DoctorCheck:
        result = self._run(
            ["adb", "-s", self._device_id, "shell", "getprop", "ro.product.model"],
            timeout_seconds=8,
        )
        model = result.stdout.strip()
        return DoctorCheck(
            name="target_device_shell",
            status="ok" if result.ok and bool(model) else "fail",
            summary="目标设备 shell 可用。" if result.ok and bool(model) else "目标设备 shell 不可用或无响应。",
            details={"device_id": self._device_id, "model": model, "command": self._command_details(result)},
        )

    def _check_target_package(self) -> DoctorCheck:
        if not self._package_name:
            return DoctorCheck(
                name="target_package",
                status="skipped",
                summary="未提供 --package-name，跳过安装包检查。",
                details={"device_id": self._device_id},
            )
        path_result = self._run(
            ["adb", "-s", self._device_id, "shell", "pm", "path", self._package_name],
            timeout_seconds=8,
        )
        installed = path_result.ok and bool(path_result.stdout.strip())
        version_result = self._run(
            ["adb", "-s", self._device_id, "shell", "dumpsys", "package", self._package_name],
            timeout_seconds=10,
        ) if installed else CommandResult(returncode=1, stderr="package not installed")
        return DoctorCheck(
            name="target_package",
            status="ok" if installed else "fail",
            summary=f"目标包 {self._package_name} 已安装。" if installed else f"目标包 {self._package_name} 未安装或不可见。",
            details={
                "device_id": self._device_id,
                "package_name": self._package_name,
                "pm_path": self._tail(path_result.stdout),
                "version_summary": self._package_version_summary(version_result.stdout),
                "pm_path_result": self._command_details(path_result),
            },
        )

    def _check_target_perfetto(self) -> DoctorCheck:
        result = self._run(
            ["adb", "-s", self._device_id, "shell", "command", "-v", "perfetto"],
            timeout_seconds=8,
        )
        available = result.ok and bool(result.stdout.strip())
        return DoctorCheck(
            name="target_perfetto_available",
            status="ok" if available else "warn",
            summary="目标设备支持 perfetto 命令。" if available else "目标设备未发现 perfetto 命令，Perfetto trace 可能不可用。",
            details={
                "device_id": self._device_id,
                "perfetto_path": result.stdout.strip(),
                "command": self._command_details(result),
            },
        )

    def _check_target_perfetto_write_permission(self) -> DoctorCheck:
        probe_path = self._target_perfetto_probe_path()
        write_result = self._run(
            ["adb", "-s", self._device_id, "shell", "perfetto", "-o", probe_path, "-t", "1s", "sched"],
            timeout_seconds=12,
        )
        ls_result = self._run(
            ["adb", "-s", self._device_id, "shell", "ls", "-l", probe_path],
            timeout_seconds=8,
        ) if write_result.ok else CommandResult(returncode=1, stderr="write failed")
        cleanup_result = self._run(
            ["adb", "-s", self._device_id, "shell", "rm", "-f", probe_path],
            timeout_seconds=8,
        ) if write_result.ok else CommandResult(returncode=0)
        ok = write_result.ok and ls_result.ok
        return DoctorCheck(
            name="target_perfetto_write_permission",
            status="ok" if ok else "fail",
            summary=(
                "目标设备可通过 perfetto 写入 trace，Perfetto 采集具备基础条件。"
                if ok
                else "目标设备无法通过 perfetto 写入 trace，Perfetto 采集可能不可用。"
            ),
            details={
                "device_id": self._device_id,
                "probe_path": probe_path,
                "write": self._command_details(write_result),
                "ls": self._command_details(ls_result),
                "cleanup": self._command_details(cleanup_result),
            },
        )

    def _target_perfetto_probe_path(self) -> str:
        token = self._safe_device_token(self._device_id)
        template = DEFAULT_PERFETTO_REMOTE_PATH_TEMPLATE
        try:
            registry = load_monitoring_profile_registry(self._config_dir / "monitoring.json")
            profiles = dict(registry.get("profiles", {}) or {})
            profile = dict(profiles.get("perfetto", {}) or {})
            metadata = dict(profile.get("metadata", {}) or {})
            template = str(metadata.get("perfetto_remote_path_template") or template)
        except Exception:
            template = DEFAULT_PERFETTO_REMOTE_PATH_TEMPLATE
        try:
            return template.format(session_name=f"asl_doctor_{token}", device_id=self._device_id)
        except Exception:
            return DEFAULT_PERFETTO_REMOTE_PATH_TEMPLATE.format(session_name=f"asl_doctor_{token}", device_id=self._device_id)

    def _check_target_wireless_reachability(self) -> DoctorCheck:
        host_port = self._split_host_port(self._device_id)
        if not host_port:
            state_result = self._run(
                ["adb", "-s", self._device_id, "get-state"],
                timeout_seconds=5,
            )
            tcpip_result = self._run(
                ["adb", "-s", self._device_id, "shell", "getprop", "service.adb.tcp.port"],
                timeout_seconds=5,
            )
            is_usb_ready = state_result.ok and state_result.stdout.strip() == "device"
            return DoctorCheck(
                name="target_wireless_adb",
                status="ok" if is_usb_ready else "fail",
                summary=(
                    "目标设备是 USB serial，ADB 已可用；无需无线 TCP 可达性检查。"
                    if is_usb_ready
                    else "目标设备是 USB serial，但 ADB 状态不可用。"
                ),
                details={
                    "device_id": self._device_id,
                    "connection_type": "usb_serial",
                    "get_state": state_result.stdout.strip(),
                    "get_state_result": self._command_details(state_result),
                    "adb_tcp_port_property": tcpip_result.stdout.strip(),
                    "tcp_port_command": self._command_details(tcpip_result),
                },
            )
        host, port = host_port
        reachable, error = self._probe_tcp(host, port)
        return DoctorCheck(
            name="target_wireless_adb",
            status="ok" if reachable else "fail",
            summary=f"无线 ADB {self._device_id} TCP 可达。" if reachable else f"无线 ADB {self._device_id} TCP 不可达。",
            details={"device_id": self._device_id, "host": host, "port": port, "reachable": reachable, "error": error},
        )

    def _run(self, command: Sequence[str], *, timeout_seconds: int) -> CommandResult:
        return self._command_runner.run(command, timeout_seconds=timeout_seconds)

    @staticmethod
    def _parse_adb_devices(output: str) -> list[dict[str, Any]]:
        devices = []
        for line in output.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("List of devices"):
                continue
            parts = stripped.split()
            if len(parts) < 2:
                continue
            devices.append(
                {
                    "serial": parts[0],
                    "status": parts[1],
                    "detail": " ".join(parts[2:]),
                }
            )
        return devices

    @staticmethod
    def _python_dependency_status() -> list[dict[str, Any]]:
        packages = [
            ("sqlalchemy", "sqlalchemy", True),
            ("pymysql", "pymysql", True),
            ("pandas", "pandas", True),
            ("numpy", "numpy", True),
            ("openpyxl", "openpyxl", True),
            ("psutil", "psutil", True),
            ("cryptography", "cryptography", True),
            ("certifi", "certifi", True),
            ("configparser", "configparser", True),
            ("cv2", "opencv-python", False),
            ("solox", "solox", False),
        ]
        result = []
        for module_name, package_name, required in packages:
            available = importlib.util.find_spec(module_name) is not None
            result.append({"module": module_name, "package": package_name, "required": required, "available": available})
        return result

    @staticmethod
    def _package_version_summary(output: str) -> dict[str, str]:
        summary: dict[str, str] = {}
        for line in output.splitlines():
            stripped = line.strip()
            if stripped.startswith(("versionName=", "versionCode=", "firstInstallTime=", "lastUpdateTime=")):
                key, _, value = stripped.partition("=")
                summary[key] = value
        return summary

    @staticmethod
    def _safe_device_token(value: str) -> str:
        return "".join(ch if ch.isalnum() else "_" for ch in str(value or ""))[:80] or "device"

    @staticmethod
    def _split_host_port(value: str) -> tuple[str, int] | None:
        if ":" not in value:
            return None
        host, raw_port = value.rsplit(":", 1)
        if not host or not raw_port.isdigit():
            return None
        return host, int(raw_port)

    @staticmethod
    def _probe_tcp(host: str, port: int) -> tuple[bool, str]:
        try:
            with socket.create_connection((host, int(port)), timeout=1.0):
                return True, ""
        except OSError as exc:
            return False, str(exc)

    def _post_feishu_doctor_ping(self, webhook: WebhookSubscription) -> dict[str, Any]:
        timestamp = self._unix_timestamp()
        body = {
            "timestamp": str(timestamp),
            "sign": self._feishu_sign(str(timestamp), str(webhook.signing_secret or "")),
            "msg_type": "text",
            "content": {
                "text": f"Android Stability Lab doctor ping\nwebhook: {webhook.name}\ntime: {now_beijing_string()}",
            },
        }
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            str(webhook.url),
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._webhook_timeout_seconds) as response:
                payload = response.read(512).decode("utf-8", errors="replace")
                return {
                    "name": webhook.name,
                    "ok": 200 <= int(response.status) < 300,
                    "status_code": int(response.status),
                    "response_excerpt": payload,
                }
        except urllib.error.HTTPError as exc:
            body = exc.read(512).decode("utf-8", errors="replace")
            return {"name": webhook.name, "ok": False, "status_code": exc.code, "response_excerpt": body}
        except Exception as exc:
            return {"name": webhook.name, "ok": False, "error": str(exc)}

    @staticmethod
    def _feishu_sign(timestamp: str, signing_secret: str) -> str:
        string_to_sign = f"{timestamp}\n{signing_secret}"
        digest = hmac.new(string_to_sign.encode("utf-8"), b"", digestmod=hashlib.sha256).digest()
        return base64.b64encode(digest).decode("utf-8")

    @staticmethod
    def _unix_timestamp() -> int:
        import time

        return int(time.time())

    @staticmethod
    def _webhook_requires_secret(webhook: WebhookSubscription) -> bool:
        url = str(webhook.url or "").strip().lower()
        if not url.startswith("https://"):
            return False
        return str(webhook.delivery_channel or "") in {"feishu_bot", "im_notify", "defect_sync", "release_submission"}

    @staticmethod
    def _webhook_summary(webhook: WebhookSubscription) -> dict[str, Any]:
        return {
            "name": webhook.name,
            "delivery_channel": webhook.delivery_channel,
            "url_host": DoctorService._url_host(webhook.url),
            "event_type_count": len(webhook.subscribed_event_types),
            "has_signing_secret": bool(str(webhook.signing_secret or "").strip()),
            "signature_key_id": webhook.signature_key_id,
        }

    @staticmethod
    def _url_host(url: str) -> str:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(str(url or ""))
            return parsed.netloc
        except Exception:
            return ""

    @staticmethod
    def _command_details(result: CommandResult) -> dict[str, Any]:
        return {
            "returncode": result.returncode,
            "stdout": DoctorService._tail(result.stdout),
            "stderr": DoctorService._tail(result.stderr),
            "timed_out": result.timed_out,
        }

    @staticmethod
    def _tail(value: str, *, limit: int = 800) -> str:
        text = str(value or "").strip()
        if len(text) <= limit:
            return text
        return text[-limit:]
