"""SQLAlchemy models for the new stability execution domain."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from stability.time_utils import utcnow

from .legacy_models import Base


class TimestampMixin:
    """Shared timestamp columns for mutable records."""

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


class DeviceRecord(Base, TimestampMixin):
    __tablename__ = "stability_devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(64), nullable=False, unique=True, index=True)
    serial_no = Column(String(128), nullable=False, unique=True, index=True)
    brand = Column(String(64), nullable=True)
    model = Column(String(128), nullable=True, index=True)
    android_version = Column(String(32), nullable=True)
    rom_version = Column(String(128), nullable=True)
    abi = Column(String(64), nullable=True)
    battery_level = Column(Float, nullable=True)
    temperature = Column(Float, nullable=True)
    online_status = Column(String(32), nullable=False, default="unknown", index=True)
    occupy_status = Column(String(32), nullable=False, default="idle", index=True)
    group_name = Column(String(64), nullable=True, index=True)
    tags_json = Column(Text, nullable=True)
    last_seen_at = Column(DateTime, nullable=True, index=True)
    last_heartbeat_at = Column(DateTime, nullable=True, index=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    extra_json = Column(Text, nullable=True)

    execution_instances = relationship(
        "ExecutionInstanceRecord",
        back_populates="device",
        foreign_keys="ExecutionInstanceRecord.device_record_id",
    )

    __table_args__ = (
        Index("idx_stability_device_status", "online_status", "occupy_status"),
        Index("idx_stability_device_group_model", "group_name", "model"),
    )


class TaskDefinitionRecord(Base, TimestampMixin):
    __tablename__ = "stability_task_definitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), nullable=False, unique=True, index=True)
    task_name = Column(String(255), nullable=False, index=True)
    package_name = Column(String(255), nullable=False, index=True)
    app_label = Column(String(255), nullable=True)
    template_type = Column(String(64), nullable=False, index=True)
    template_params_json = Column(Text, nullable=True)
    device_selector_json = Column(Text, nullable=True)
    sampling_config_json = Column(Text, nullable=True)
    duration_sec = Column(Integer, nullable=True)
    sampling_interval_sec = Column(Integer, nullable=True)
    timeout_seconds = Column(Integer, nullable=True)
    created_by = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default="draft", index=True)
    summary = Column(Text, nullable=True)

    task_runs = relationship(
        "TaskRunRecord",
        back_populates="task_definition",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_stability_task_package_template", "package_name", "template_type"),
    )


class TaskRunRecord(Base, TimestampMixin):
    __tablename__ = "stability_task_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, unique=True, index=True)
    task_definition_id = Column(
        Integer,
        ForeignKey("stability_task_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_status = Column(String(32), nullable=False, default="queued", index=True)
    planned_device_count = Column(Integer, nullable=False, default=0)
    completed_instance_count = Column(Integer, nullable=False, default=0)
    success_instance_count = Column(Integer, nullable=False, default=0)
    failed_instance_count = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, nullable=True, index=True)
    finished_at = Column(DateTime, nullable=True, index=True)
    summary = Column(Text, nullable=True)

    task_definition = relationship("TaskDefinitionRecord", back_populates="task_runs")
    execution_instances = relationship(
        "ExecutionInstanceRecord",
        back_populates="task_run",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_stability_task_run_status_time", "run_status", "started_at"),
        Index("idx_stability_task_run_definition_status", "task_definition_id", "run_status"),
    )


class ExecutionInstanceRecord(Base, TimestampMixin):
    __tablename__ = "stability_execution_instances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instance_id = Column(String(64), nullable=False, unique=True, index=True)
    task_run_id = Column(
        Integer,
        ForeignKey("stability_task_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    device_record_id = Column(
        Integer,
        ForeignKey("stability_devices.id", ondelete="RESTRICT"),
        nullable=False,
    )
    monitoring_session_id = Column(
        Integer,
        ForeignKey("monitoring_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = Column(String(32), nullable=False, default="pending", index=True)
    result = Column(String(32), nullable=True, index=True)
    result_level = Column(String(32), nullable=True, index=True)
    exit_reason = Column(String(64), nullable=True, index=True)
    device_snapshot_json = Column(Text, nullable=True)
    queued_at = Column(DateTime, nullable=True, index=True)
    started_at = Column(DateTime, nullable=True, index=True)
    finished_at = Column(DateTime, nullable=True, index=True)
    timeout_at = Column(DateTime, nullable=True, index=True)
    first_issue_at = Column(DateTime, nullable=True, index=True)
    exception_count = Column(Integer, nullable=False, default=0)
    report_path = Column(Text, nullable=True)
    log_path = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)

    task_run = relationship("TaskRunRecord", back_populates="execution_instances")
    device = relationship(
        "DeviceRecord",
        back_populates="execution_instances",
        foreign_keys=[device_record_id],
    )
    issues = relationship(
        "IssueRecordModel",
        back_populates="execution_instance",
        cascade="all, delete-orphan",
    )
    artifacts = relationship(
        "ArtifactRecordModel",
        back_populates="execution_instance",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_stability_instance_run_status", "task_run_id", "status"),
        Index("idx_stability_instance_device_status", "device_record_id", "status"),
        Index("idx_stability_instance_run_device", "task_run_id", "device_record_id"),
    )


class IssueRecordModel(Base, TimestampMixin):
    __tablename__ = "stability_issue_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(String(64), nullable=False, unique=True, index=True)
    execution_instance_id = Column(
        Integer,
        ForeignKey("stability_execution_instances.id", ondelete="CASCADE"),
        nullable=False,
    )
    issue_type = Column(String(64), nullable=False, index=True)
    issue_title = Column(String(255), nullable=False)
    severity = Column(String(32), nullable=False, default="medium", index=True)
    source = Column(String(64), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="open", index=True)
    raw_key = Column(String(255), nullable=True, index=True)
    summary = Column(Text, nullable=True)
    detected_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    resolved_at = Column(DateTime, nullable=True)
    payload_json = Column(Text, nullable=True)

    execution_instance = relationship("ExecutionInstanceRecord", back_populates="issues")
    artifacts = relationship(
        "ArtifactRecordModel",
        back_populates="issue",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_stability_issue_instance_detected", "execution_instance_id", "detected_at"),
        Index("idx_stability_issue_type_severity", "issue_type", "severity"),
    )


class ArtifactRecordModel(Base, TimestampMixin):
    __tablename__ = "stability_artifact_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artifact_id = Column(String(64), nullable=False, unique=True, index=True)
    execution_instance_id = Column(
        Integer,
        ForeignKey("stability_execution_instances.id", ondelete="CASCADE"),
        nullable=False,
    )
    issue_record_id = Column(
        Integer,
        ForeignKey("stability_issue_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    artifact_type = Column(String(64), nullable=False, index=True)
    file_path = Column(Text, nullable=False)
    file_name = Column(String(255), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    capture_reason = Column(String(64), nullable=True, index=True)
    capture_status = Column(String(32), nullable=False, default="captured", index=True)
    content_type = Column(String(128), nullable=True)
    captured_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    metadata_json = Column(Text, nullable=True)

    execution_instance = relationship("ExecutionInstanceRecord", back_populates="artifacts")
    issue = relationship("IssueRecordModel", back_populates="artifacts")

    __table_args__ = (
        Index(
            "idx_stability_artifact_instance_captured",
            "execution_instance_id",
            "captured_at",
        ),
        Index("idx_stability_artifact_issue_type", "issue_record_id", "artifact_type"),
    )


__all__ = [
    "ArtifactRecordModel",
    "DeviceRecord",
    "ExecutionInstanceRecord",
    "IssueRecordModel",
    "TaskDefinitionRecord",
    "TaskRunRecord",
]
