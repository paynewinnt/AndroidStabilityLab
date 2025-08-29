from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from stability.infrastructure.persistence import DatabaseConnectionManager, db_manager
from stability.infrastructure.persistence import (
    ArtifactRecordModel,
    DeviceRecord,
    ExecutionInstanceRecord,
    TaskDefinitionRecord,
    TaskRunRecord,
)
from stability.domain import AppError, AppErrorCode, ExecutionInstance, TaskDefinition, TaskRun

from .mappers import (
    artifact_to_record,
    device_from_record,
    device_to_record,
    device_record_from_snapshot,
    issue_to_record,
    instance_from_record,
    instance_to_record,
    run_from_record,
    run_to_record,
    task_from_record,
    task_to_record,
)


class _SQLAlchemyRepositoryBase:
    def __init__(self, connection_manager: DatabaseConnectionManager | None = None) -> None:
        self._connection_manager = connection_manager or db_manager

    @contextmanager
    def _session(self) -> Iterator[Session]:
        self._ensure_connected()
        with self._connection_manager.get_session() as session:
            yield session

    def _ensure_connected(self) -> None:
        if self._connection_manager.is_connected():
            return
        if not self._connection_manager.connect():
            raise AppError(AppErrorCode.INTERNAL_ERROR, "Unable to connect to the configured database.")


class SQLAlchemyDeviceRepository(_SQLAlchemyRepositoryBase):
    def add(self, device):
        return self.save(device)

    def get(self, device_id: str):
        with self._session() as session:
            record = self._find_record(session, device_id)
            return device_from_record(record) if record is not None else None

    def list(self):
        with self._session() as session:
            records = session.execute(
                select(DeviceRecord).order_by(DeviceRecord.updated_at.desc(), DeviceRecord.id.desc())
            ).scalars()
            return tuple(device_from_record(record) for record in records)

    def save(self, device):
        with self._session() as session:
            record = self._find_record(session, device.device_id)
            mapped = device_to_record(device, record=record)
            session.add(mapped)
            session.flush()
            session.refresh(mapped)
            return device_from_record(mapped)

    @staticmethod
    def _find_record(session: Session, device_id: str) -> DeviceRecord | None:
        return session.execute(
            select(DeviceRecord).where(DeviceRecord.device_id == device_id)
        ).scalar_one_or_none()


class SQLAlchemyTaskRepository(_SQLAlchemyRepositoryBase):
    def add(self, task: TaskDefinition) -> TaskDefinition:
        return self.save(task)

    def get(self, task_id: str) -> TaskDefinition | None:
        with self._session() as session:
            record = self._find_record(session, task_id)
            return task_from_record(record) if record is not None else None

    def list(self) -> Sequence[TaskDefinition]:
        with self._session() as session:
            records = session.execute(
                select(TaskDefinitionRecord).order_by(TaskDefinitionRecord.created_at.desc())
            ).scalars()
            return tuple(task_from_record(record) for record in records)

    def save(self, task: TaskDefinition) -> TaskDefinition:
        with self._session() as session:
            record = self._find_record(session, task.task_id)
            mapped = task_to_record(task, record=record)
            session.add(mapped)
            session.flush()
            session.refresh(mapped)
            return task_from_record(mapped)

    @staticmethod
    def _find_record(session: Session, task_id: str) -> TaskDefinitionRecord | None:
        return session.execute(
            select(TaskDefinitionRecord).where(TaskDefinitionRecord.task_id == task_id)
        ).scalar_one_or_none()


class SQLAlchemyRunRepository(_SQLAlchemyRepositoryBase):
    def add(self, run: TaskRun) -> TaskRun:
        return self.save(run)

    def get(self, run_id: str) -> TaskRun | None:
        with self._session() as session:
            record = self._find_record(session, run_id)
            return run_from_record(record) if record is not None else None

    def list(self) -> Sequence[TaskRun]:
        with self._session() as session:
            records = session.execute(
                select(TaskRunRecord)
                .options(joinedload(TaskRunRecord.task_definition))
                .order_by(TaskRunRecord.created_at.desc(), TaskRunRecord.id.desc())
            ).unique().scalars()
            return tuple(run_from_record(record) for record in records)

    def save(self, run: TaskRun) -> TaskRun:
        with self._session() as session:
            task_record = self._find_task_record(session, run.task_definition_id)
            if task_record is None:
                raise AppError.not_found(
                    f"Task definition '{run.task_definition_id}' must exist before saving run '{run.run_id}'."
                )

            record = self._find_record(session, run.run_id)
            mapped = run_to_record(run, task_definition_pk=task_record.id, record=record)
            session.add(mapped)
            session.flush()
            persisted = self._find_record(session, run.run_id)
            if persisted is None:
                raise AppError.not_found(f"Run '{run.run_id}' was not persisted.")
            return run_from_record(persisted)

    @staticmethod
    def _find_task_record(session: Session, task_id: str) -> TaskDefinitionRecord | None:
        return session.execute(
            select(TaskDefinitionRecord).where(TaskDefinitionRecord.task_id == task_id)
        ).scalar_one_or_none()

    @staticmethod
    def _find_record(session: Session, run_id: str) -> TaskRunRecord | None:
        return (
            session.execute(
                select(TaskRunRecord)
                .options(joinedload(TaskRunRecord.task_definition))
                .where(TaskRunRecord.run_id == run_id)
            )
            .unique()
            .scalar_one_or_none()
        )


class SQLAlchemyInstanceRepository(_SQLAlchemyRepositoryBase):
    def add_many(self, instances: Sequence[ExecutionInstance]) -> Sequence[ExecutionInstance]:
        if not instances:
            return ()

        with self._session() as session:
            instance_ids: list[str] = []
            for instance in instances:
                task_run_record = self._find_run_record(session, instance.run_id)
                if task_run_record is None:
                    raise AppError.not_found(
                        f"Task run '{instance.run_id}' must exist before saving instance '{instance.instance_id}'."
                    )

                device_record = self._find_device_record(session, instance.device_id)
                if device_record is None:
                    device_record = device_record_from_snapshot(instance.device_id, instance.device_snapshot)
                    session.add(device_record)
                    session.flush()

                record = self._find_record(session, instance.instance_id)
                mapped = instance_to_record(
                    instance,
                    task_run_pk=task_run_record.id,
                    device_record_pk=device_record.id,
                    record=record,
                )
                session.add(mapped)
                session.flush()
                self._sync_issue_records(session, mapped, getattr(instance, "issues", ()))
                self._sync_artifact_records(session, mapped, getattr(instance, "artifacts", ()))
                instance_ids.append(instance.instance_id)

            session.flush()
            persisted = session.execute(
                select(ExecutionInstanceRecord)
                .options(
                    joinedload(ExecutionInstanceRecord.task_run).joinedload(TaskRunRecord.task_definition),
                    joinedload(ExecutionInstanceRecord.device),
                    joinedload(ExecutionInstanceRecord.issues),
                    joinedload(ExecutionInstanceRecord.artifacts).joinedload(ArtifactRecordModel.issue),
                )
                .where(ExecutionInstanceRecord.instance_id.in_(instance_ids))
                .order_by(ExecutionInstanceRecord.created_at.asc())
            ).unique().scalars()
            return tuple(instance_from_record(record) for record in persisted)

    def save(self, instance: ExecutionInstance) -> ExecutionInstance:
        saved = self.add_many([instance])
        if not saved:
            raise AppError.not_found(f"Instance '{instance.instance_id}' was not persisted.")
        return saved[0]

    def list_by_run(self, run_id: str) -> Sequence[ExecutionInstance]:
        with self._session() as session:
            task_run_record = self._find_run_record(session, run_id)
            if task_run_record is None:
                return ()

            records = session.execute(
                select(ExecutionInstanceRecord)
                .options(
                    joinedload(ExecutionInstanceRecord.task_run).joinedload(TaskRunRecord.task_definition),
                    joinedload(ExecutionInstanceRecord.device),
                    joinedload(ExecutionInstanceRecord.issues),
                    joinedload(ExecutionInstanceRecord.artifacts).joinedload(ArtifactRecordModel.issue),
                )
                .where(ExecutionInstanceRecord.task_run_id == task_run_record.id)
                .order_by(ExecutionInstanceRecord.created_at.asc())
            ).unique().scalars()
            return tuple(instance_from_record(record) for record in records)

    @staticmethod
    def _find_run_record(session: Session, run_id: str) -> TaskRunRecord | None:
        return session.execute(
            select(TaskRunRecord)
            .options(joinedload(TaskRunRecord.task_definition))
            .where(TaskRunRecord.run_id == run_id)
        ).unique().scalar_one_or_none()

    @staticmethod
    def _find_device_record(session: Session, device_id: str) -> DeviceRecord | None:
        return session.execute(
            select(DeviceRecord).where(DeviceRecord.device_id == device_id)
        ).scalar_one_or_none()

    @staticmethod
    def _find_record(session: Session, instance_id: str) -> ExecutionInstanceRecord | None:
        return (
            session.execute(
                select(ExecutionInstanceRecord)
                .options(
                    joinedload(ExecutionInstanceRecord.task_run).joinedload(TaskRunRecord.task_definition),
                    joinedload(ExecutionInstanceRecord.device),
                    joinedload(ExecutionInstanceRecord.issues),
                    joinedload(ExecutionInstanceRecord.artifacts).joinedload(ArtifactRecordModel.issue),
                )
                .where(ExecutionInstanceRecord.instance_id == instance_id)
            )
            .unique()
            .scalar_one_or_none()
        )

    @staticmethod
    def _sync_issue_records(session: Session, record: ExecutionInstanceRecord, issues: Sequence) -> None:
        """Persist the current domain issue list as the authoritative issue set for an instance."""
        existing_by_id = {item.issue_id: item for item in list(record.issues)}
        keep_ids: set[str] = set()

        for issue in issues:
            keep_ids.add(issue.issue_id)
            mapped = issue_to_record(
                issue,
                execution_instance_pk=record.id,
                record=existing_by_id.get(issue.issue_id),
            )
            mapped.execution_instance = record
            session.add(mapped)

        for issue_id, existing in existing_by_id.items():
            if issue_id in keep_ids:
                continue
            session.delete(existing)

    @staticmethod
    def _sync_artifact_records(session: Session, record: ExecutionInstanceRecord, artifacts: Sequence) -> None:
        """Persist the current domain artifact list as the authoritative artifact set for an instance."""
        existing_by_id = {item.artifact_id: item for item in list(record.artifacts)}
        issue_pk_by_issue_id = {item.issue_id: item.id for item in list(record.issues)}
        keep_ids: set[str] = set()

        for artifact in artifacts:
            keep_ids.add(artifact.artifact_id)
            mapped = artifact_to_record(
                artifact,
                execution_instance_pk=record.id,
                issue_record_pk=issue_pk_by_issue_id.get(artifact.issue_id),
                record=existing_by_id.get(artifact.artifact_id),
            )
            mapped.execution_instance = record
            session.add(mapped)

        for artifact_id, existing in existing_by_id.items():
            if artifact_id in keep_ids:
                continue
            session.delete(existing)
