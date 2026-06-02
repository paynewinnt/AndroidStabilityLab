from __future__ import annotations

from pathlib import Path
from typing import Iterable

from stability.app import ConfigProvider
from stability.domain import AppError, AppErrorCode, Device
from stability.execution import ExecutionStateMachine, LifecycleHookRegistry
from stability.infrastructure import (
    ADBCollectorDeviceAdapter,
    FileBackedRuleConfigProvider,
    PersistedMonitoringDataProvider,
    build_monitoring_adapter,
    default_analysis_rule_config,
)
from stability.repositories import (
    InMemoryDeviceRepository,
    InMemoryInstanceRepository,
    InMemoryRunRepository,
    InMemoryTaskRepository,
    StaticDevicePlanner,
)

from .bootstrap_factories import (
    NullDiscoveryAdapter,
    NullMonitoringDataProvider,
    RepositoryBackedDevicePlanner,
    build_analysis_services,
    build_default_scenario_runners,
    build_device_service,
    build_integration_services,
    build_outbox_service,
    build_runtime_services,
    build_task_services,
    build_web_bundle,
)
from .bootstrap_types import DeviceSelector, V1BootstrapBundle


def _build_persistent_monitoring_adapter(
    *,
    monitoring_backend: str | None = None,
    monitoring_config_path: str | Path | None = None,
    config_provider: ConfigProvider | None = None,
):
    provider = config_provider or ConfigProvider()
    settings = provider.monitoring_settings(
        requested_backend=monitoring_backend,
        config_path=monitoring_config_path,
    )
    return build_monitoring_adapter(
        requested_backend=monitoring_backend,
        settings=settings,
    )


def create_v1_bootstrap(
    devices: Iterable[Device] | None = None,
    *,
    config_provider: ConfigProvider | None = None,
) -> V1BootstrapBundle:
    """Build an in-memory V1 runtime for smoke tests and fast local development."""
    config = config_provider or ConfigProvider()
    paths = config.runtime_paths()
    device_map = {device.device_id: device for device in (devices or [])}

    device_repository = InMemoryDeviceRepository()
    for device in device_map.values():
        device_repository.add(device)
    task_repository = InMemoryTaskRepository()
    run_repository = InMemoryRunRepository()
    instance_repository = InMemoryInstanceRepository()
    planner = StaticDevicePlanner(devices=device_map)
    hooks = LifecycleHookRegistry()
    state_machine = ExecutionStateMachine()

    device_service = build_device_service(
        repository=device_repository,
        discovery_adapter=NullDiscoveryAdapter(),
    )
    outbox_service = build_outbox_service(outbox_config=config.outbox())
    task_services = build_task_services(
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
        planner=planner,
        hooks=hooks,
        state_machine=state_machine,
        paths=paths,
        audit_event_sink=outbox_service,
        monitoring_adapter=None,
        instance_factory_devices=device_map,
    )
    analysis_services = build_analysis_services(
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
        paths=paths,
        rule_config=default_analysis_rule_config(),
        monitoring_data_provider=NullMonitoringDataProvider(),
        config_provider=config,
    )
    integration_services = build_integration_services(
        paths=paths,
        outbox_service=outbox_service,
        task_services=task_services,
        analysis_services=analysis_services,
        config_provider=config,
    )
    runtime_services = build_runtime_services(
        paths=paths,
        device_service=device_service,
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
        task_services=task_services,
        outbox_service=outbox_service,
        config_provider=config,
    )
    return build_web_bundle(
        task_services=task_services,
        analysis_services=analysis_services,
        integration_services=integration_services,
        runtime_services=runtime_services,
        outbox_service=outbox_service,
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
        planner=planner,
        hooks=hooks,
        state_machine=state_machine,
        device_service=device_service,
        devices=device_map,
    )


def create_v1_persistent_bootstrap(
    *,
    monitoring_backend: str | None = None,
    monitoring_config_path: str | Path | None = None,
    config_provider: ConfigProvider | None = None,
) -> V1BootstrapBundle:
    """Build a database-backed runtime wired to ADB and monitoring adapters."""
    config = config_provider or ConfigProvider()
    paths = config.runtime_paths()
    try:
        from stability.infrastructure.persistence import db_manager
        from stability.repositories.sqlalchemy import (
            SQLAlchemyDeviceRepository,
            SQLAlchemyInstanceRepository,
            SQLAlchemyRunRepository,
            SQLAlchemyTaskRepository,
        )
    except (
        ModuleNotFoundError
    ) as exc:  # pragma: no cover - depends on runtime environment
        raise AppError(
            AppErrorCode.INTERNAL_ERROR,
            "Persistent V1 bootstrap requires optional database dependencies such as sqlalchemy.",
        ) from exc

    if not db_manager.is_connected() and not db_manager.connect():
        raise AppError(
            AppErrorCode.INTERNAL_ERROR, "Unable to connect to the configured database."
        )

    task_repository = SQLAlchemyTaskRepository(db_manager)
    run_repository = SQLAlchemyRunRepository(db_manager)
    instance_repository = SQLAlchemyInstanceRepository(db_manager)
    device_repository = SQLAlchemyDeviceRepository(db_manager)
    planner = RepositoryBackedDevicePlanner(device_repository)
    hooks = LifecycleHookRegistry()
    state_machine = ExecutionStateMachine()

    monitoring_adapter, resolved_monitoring_backend = (
        _build_persistent_monitoring_adapter(
            monitoring_backend=monitoring_backend,
            monitoring_config_path=monitoring_config_path,
            config_provider=config,
        )
    )
    device_service = build_device_service(
        repository=device_repository,
        discovery_adapter=ADBCollectorDeviceAdapter(),
    )
    outbox_service = build_outbox_service(outbox_config=config.outbox())
    task_services = build_task_services(
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
        planner=planner,
        hooks=hooks,
        state_machine=state_machine,
        paths=paths,
        audit_event_sink=outbox_service,
        monitoring_adapter=monitoring_adapter,
    )
    analysis_services = build_analysis_services(
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
        paths=paths,
        rule_config=FileBackedRuleConfigProvider("config/stability_rules.json").load(),
        monitoring_data_provider=PersistedMonitoringDataProvider(),
        config_provider=config,
    )
    integration_services = build_integration_services(
        paths=paths,
        outbox_service=outbox_service,
        task_services=task_services,
        analysis_services=analysis_services,
        monitoring_backend=resolved_monitoring_backend,
        config_provider=config,
    )
    runtime_services = build_runtime_services(
        paths=paths,
        device_service=device_service,
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
        task_services=task_services,
        outbox_service=outbox_service,
        config_provider=config,
    )
    devices = {device.device_id: device for device in device_repository.list()}
    return build_web_bundle(
        task_services=task_services,
        analysis_services=analysis_services,
        integration_services=integration_services,
        runtime_services=runtime_services,
        outbox_service=outbox_service,
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
        planner=planner,
        hooks=hooks,
        state_machine=state_machine,
        device_service=device_service,
        devices=devices,
        monitoring_backend=resolved_monitoring_backend,
    )


__all__ = [
    "DeviceSelector",
    "RepositoryBackedDevicePlanner",
    "V1BootstrapBundle",
    "build_default_scenario_runners",
    "create_v1_bootstrap",
    "create_v1_persistent_bootstrap",
]
