from __future__ import annotations

from enum import Enum


class DomainEnum(str, Enum):
    """Shared base class for serializable domain enums."""

    def __str__(self) -> str:
        return self.value


class DeviceConnectionState(DomainEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNAUTHORIZED = "unauthorized"
    UNKNOWN = "unknown"


class DeviceAvailabilityState(DomainEnum):
    IDLE = "idle"
    RESERVED = "reserved"
    RUNNING = "running"
    ERROR = "error"
    QUARANTINED = "quarantined"


class TaskTemplateType(DomainEnum):
    MONKEY = "monkey"
    COLD_START_LOOP = "cold_start_loop"
    FOREGROUND_BACKGROUND_LOOP = "foreground_background_loop"
    INSTALL_UNINSTALL_LOOP = "install_uninstall_loop"
    REBOOT_LOOP = "reboot_loop"
    STANDBY_WAKE_LOOP = "standby_wake_loop"
    CUSTOM = "custom"


class TaskRunStatus(DomainEnum):
    DRAFT = "draft"
    QUEUED = "queued"
    RUNNING = "running"
    PARTIAL_FAILED = "partial_failed"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {
            TaskRunStatus.SUCCESS,
            TaskRunStatus.FAILED,
            TaskRunStatus.CANCELLED,
            TaskRunStatus.PARTIAL_FAILED,
        }


class ExecutionStatus(DomainEnum):
    PENDING = "pending"
    PRECHECK_FAILED = "precheck_failed"
    PREPARING = "preparing"
    RUNNING = "running"
    STOPPING = "stopping"
    COLLECTING = "collecting"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {
            ExecutionStatus.PRECHECK_FAILED,
            ExecutionStatus.SUCCESS,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
        }

    @property
    def is_active(self) -> bool:
        return self in {
            ExecutionStatus.PREPARING,
            ExecutionStatus.RUNNING,
            ExecutionStatus.STOPPING,
            ExecutionStatus.COLLECTING,
        }


class ExitReason(DomainEnum):
    COMPLETED = "completed"
    USER_STOPPED = "user_stopped"
    CANCELLED = "cancelled"
    PRECHECK_FAILED = "precheck_failed"
    EXECUTION_ERROR = "execution_error"
    DEVICE_OFFLINE = "device_offline"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class ResultLevel(DomainEnum):
    PASSED = "passed"
    UNSTABLE = "unstable"
    FAILED = "failed"
    UNKNOWN = "unknown"


class IssueType(DomainEnum):
    CRASH = "crash"
    ANR = "anr"
    JAVA_EXCEPTION = "java_exception"
    JAVA_CRASH = "java_crash"
    NATIVE_CRASH = "native_crash"
    SYSTEM_SERVER_CRASH = "system_server_crash"
    WATCHDOG = "watchdog"
    FREEZE = "freeze"
    BLACK_SCREEN = "black_screen"
    REBOOT = "reboot"
    PROCESS_EXIT = "process_exit"
    STARTUP_FAILURE = "startup_failure"
    STARTUP_TIMEOUT = "startup_timeout"
    EXECUTION_TIMEOUT = "execution_timeout"
    DEVICE_OFFLINE = "device_offline"


class SeverityLevel(DomainEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ArtifactType(DomainEnum):
    LOGCAT = "logcat"
    BUGREPORT = "bugreport"
    DROPBOX = "dropbox"
    DUMPSYS_MEMINFO = "dumpsys_meminfo"
    DUMPSYS_SURFACEFLINGER = "dumpsys_surfaceflinger"
    SCREENSHOT = "screenshot"
    INPUT_EVENTS = "input_events"
    PERFETTO_TRACE = "perfetto_trace"
    TRACES = "traces"
    TOMBSTONE = "tombstone"
    EXECUTION_LOG = "execution_log"
    PERFORMANCE_SNAPSHOT = "performance_snapshot"


class ArtifactCaptureStatus(DomainEnum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class MetricType(DomainEnum):
    CPU = "cpu"
    MEMORY = "memory"
    FPS = "fps"
    NETWORK = "network"
    BATTERY = "battery"
    POWER = "power"
    STARTUP = "startup"
    CUSTOM = "custom"
