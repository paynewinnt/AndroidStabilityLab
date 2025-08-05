"""Repository and factory helpers for the V1 bootstrap stage."""

from .memory import (
    DomainExecutionInstanceFactory,
    DomainTaskRunFactory,
    InMemoryDeviceRepository,
    InMemoryInstanceRepository,
    InMemoryRunRepository,
    InMemoryTaskRepository,
    StaticDevicePlanner,
)

try:
    from .sqlalchemy import (
        SQLAlchemyDeviceRepository,
        SQLAlchemyInstanceRepository,
        SQLAlchemyRunRepository,
        SQLAlchemyTaskRepository,
    )
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    SQLAlchemyDeviceRepository = None
    SQLAlchemyInstanceRepository = None
    SQLAlchemyRunRepository = None
    SQLAlchemyTaskRepository = None

__all__ = [
    "DomainExecutionInstanceFactory",
    "DomainTaskRunFactory",
    "InMemoryDeviceRepository",
    "InMemoryInstanceRepository",
    "InMemoryRunRepository",
    "InMemoryTaskRepository",
    "StaticDevicePlanner",
]

if SQLAlchemyDeviceRepository is not None:
    __all__.extend(
        [
            "SQLAlchemyDeviceRepository",
            "SQLAlchemyInstanceRepository",
            "SQLAlchemyRunRepository",
            "SQLAlchemyTaskRepository",
        ]
    )
