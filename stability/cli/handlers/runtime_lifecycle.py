from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from stability.app import ConfigProvider, DoctorService, PlatformHealthService, RuntimeLifecycleService


def _split_values(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for raw in values:
        for item in str(raw or "").split(","):
            value = item.strip()
            if value:
                result.append(value)
    return result


def _handle_runtime_doctor(args: argparse.Namespace) -> int:
    provider = ConfigProvider(config_dir=str(getattr(args, "config_dir", "") or "config"))
    runtime_root = str(getattr(args, "runtime_root", "") or provider.runtime_paths().root)
    service = RuntimeLifecycleService(root_dir=runtime_root)
    result = service.doctor()
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0 if result.ok else 1


def _handle_doctor(args: argparse.Namespace) -> int:
    provider = ConfigProvider(config_dir=str(getattr(args, "config_dir", "") or "config"))
    paths = provider.runtime_paths()
    web_config = provider.web()
    outbox_config = provider.outbox()
    service = DoctorService(
        runtime_root=str(getattr(args, "runtime_root", "") or paths.root),
        config_dir=str(provider.config_dir),
        web_host=str(getattr(args, "web_host", "") or web_config.host),
        web_port=int(getattr(args, "web_port", None) or web_config.port),
        outbox_root=str(getattr(args, "outbox_root", "") or outbox_config.root_dir),
        device_id=str(getattr(args, "device_id", "") or ""),
        package_name=str(getattr(args, "package_name", "") or ""),
        check_webhooks=bool(args.check_webhooks),
    )
    result = service.run()
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0 if result.ok else 1


def _handle_platform_health(args: argparse.Namespace) -> int:
    provider = ConfigProvider(config_dir=str(getattr(args, "config_dir", "") or "config"))
    runtime_root = getattr(args, "runtime_root", "") or provider.runtime_paths().root
    try:
        from stability.bootstrap import create_v1_persistent_bootstrap

        service = create_v1_persistent_bootstrap(config_provider=provider).platform_health_service
    except Exception:
        service = PlatformHealthService(root_dir=Path(runtime_root) / "platform_health", thresholds=provider.platform_health())
    snapshot = service.snapshot(record=not bool(getattr(args, "no_record", False)))
    payload = service.snapshot_payload(snapshot)
    if bool(getattr(args, "publish_alert", False)):
        published = service.publish_alert(snapshot)
        payload["published_alert"] = {
            "published": published is not None,
            "alert": published.to_payload() if published is not None else None,
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if snapshot.ok else 1


def _handle_export_runtime(args: argparse.Namespace) -> int:
    provider = ConfigProvider(config_dir=str(getattr(args, "config_dir", "") or "config"))
    runtime_root = str(getattr(args, "runtime_root", "") or provider.runtime_paths().root)
    service = RuntimeLifecycleService(root_dir=runtime_root)
    result = service.export(args.output, categories=_split_values(args.categories))
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0


def _handle_cleanup_runtime(args: argparse.Namespace) -> int:
    provider = ConfigProvider(config_dir=str(getattr(args, "config_dir", "") or "config"))
    runtime_root = str(getattr(args, "runtime_root", "") or provider.runtime_paths().root)
    service = RuntimeLifecycleService(root_dir=runtime_root)
    result = service.cleanup(
        categories=_split_values(args.categories),
        max_age_days=args.max_age_days,
        apply=bool(args.apply),
    )
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0


def _handle_cleanup_evidence(args: argparse.Namespace) -> int:
    provider = ConfigProvider(config_dir=str(getattr(args, "config_dir", "") or "config"))
    runtime_root = str(getattr(args, "runtime_root", "") or provider.runtime_paths().root)
    service = RuntimeLifecycleService(root_dir=runtime_root)
    result = service.enforce_evidence_retention(
        policy=provider.evidence_retention(),
        apply=bool(args.apply),
    )
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0
