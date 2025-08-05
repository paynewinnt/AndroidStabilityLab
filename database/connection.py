"""Public wrapper for the persistence connection manager."""

from stability.infrastructure.persistence.connection import DatabaseConnectionManager, db_manager

STABLE_API_SHIM = True

__all__ = ["DatabaseConnectionManager", "STABLE_API_SHIM", "db_manager"]
