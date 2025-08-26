from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


QuickAdbParam = Literal["package", "bugreport_path"]


@dataclass(frozen=True)
class QuickAdbCommand:
    command_id: str
    title: str
    description: str
    layer: str
    group: str
    args: tuple[str, ...]
    params: tuple[QuickAdbParam, ...] = ()
    timeout_seconds: int = 20
    risk: str = "safe"

    def render_args(self, *, package_name: str = "", artifact_dir: Path | None = None) -> tuple[str, ...]:
        values = {
            "package": package_name,
            "bugreport_path": str((artifact_dir or Path("runtime/quick_adb")) / "bugreport.zip"),
        }
        rendered: list[str] = []
        for arg in self.args:
            value = arg
            for key, replacement in values.items():
                value = value.replace("{" + key + "}", replacement)
            rendered.append(value)
        return tuple(rendered)


QUICK_ADB_LAYERS: tuple[dict[str, str], ...] = (
    {"key": "app", "label": "App 层", "bridge": "Java / Kotlin API"},
    {"key": "framework", "label": "Framework 层", "bridge": "Binder IPC"},
    {"key": "system_server", "label": "System Server / 系统服务", "bridge": "Binder / Socket / Native 调用"},
    {"key": "native_service", "label": "Native Service / 系统 Native 组件", "bridge": "HIDL / AIDL HAL / JNI / ioctl / sysfs"},
    {"key": "hal", "label": "HAL 层", "bridge": "驱动接口"},
    {"key": "kernel", "label": "Kernel / Driver 层", "bridge": "内核日志 / procfs / sysfs / pstore"},
    {"key": "hardware", "label": "硬件", "bridge": "由上层状态和内核证据间接定位"},
)


QUICK_ADB_COMMANDS: tuple[QuickAdbCommand, ...] = (
    QuickAdbCommand(
        "app_processes",
        "查看全部进程",
        "确认 App 进程、系统进程是否存在，以及进程名/PID 基线。",
        "app",
        "进程与前台状态",
        ("shell", "ps", "-A"),
    ),
    QuickAdbCommand(
        "app_top_once",
        "Top 快照",
        "抓取一次 CPU/线程占用快照，避免 Web 请求长时间挂住。",
        "app",
        "进程与前台状态",
        ("shell", "top", "-n", "1"),
        timeout_seconds=12,
    ),
    QuickAdbCommand(
        "app_activity_top",
        "当前前台 Activity",
        "查看当前 resumed/top activity 和 task 栈摘要。",
        "app",
        "进程与前台状态",
        ("shell", "dumpsys", "activity", "top"),
    ),
    QuickAdbCommand(
        "app_meminfo_package",
        "App 内存详情",
        "按包名查看 PSS、Dalvik/native heap、对象和图形内存。",
        "app",
        "包与权限",
        ("shell", "dumpsys", "meminfo", "{package}"),
        params=("package",),
        timeout_seconds=25,
    ),
    QuickAdbCommand(
        "app_package",
        "Package 信息",
        "按包名查看安装路径、版本、组件、签名和授权状态。",
        "app",
        "包与权限",
        ("shell", "dumpsys", "package", "{package}"),
        params=("package",),
    ),
    QuickAdbCommand(
        "app_ops",
        "AppOps 状态",
        "按包名查看敏感权限/后台行为的 AppOps 开关。",
        "app",
        "包与权限",
        ("shell", "dumpsys", "appops", "{package}"),
        params=("package",),
    ),
    QuickAdbCommand(
        "framework_activity",
        "ActivityManager 全量",
        "查看 Activity、Task、Service、Provider 和进程调度状态。",
        "framework",
        "核心 Framework 服务",
        ("shell", "dumpsys", "activity"),
        timeout_seconds=25,
    ),
    QuickAdbCommand(
        "framework_window",
        "WindowManager",
        "查看焦点窗口、窗口层级、输入目标和可见性。",
        "framework",
        "核心 Framework 服务",
        ("shell", "dumpsys", "window"),
    ),
    QuickAdbCommand(
        "framework_input",
        "InputManager",
        "查看输入设备、分发状态、焦点和事件通道。",
        "framework",
        "核心 Framework 服务",
        ("shell", "dumpsys", "input"),
    ),
    QuickAdbCommand(
        "framework_permissions",
        "Permission 状态",
        "查看系统权限定义、授权和运行时权限状态。",
        "framework",
        "包与权限",
        ("shell", "dumpsys", "permission"),
    ),
    QuickAdbCommand(
        "system_server_process",
        "system_server 进程",
        "确认 system_server 是否存在及 PID，辅助判断系统服务重启。",
        "system_server",
        "系统服务进程",
        ("shell", "sh", "-c", "ps -A | grep system_server"),
    ),
    QuickAdbCommand(
        "system_power",
        "PowerManager",
        "查看 wakelock、休眠、亮屏和电源状态。",
        "system_server",
        "电源与显示",
        ("shell", "dumpsys", "power"),
    ),
    QuickAdbCommand(
        "system_display",
        "DisplayManager",
        "查看显示设备、刷新率、亮度和 display state。",
        "system_server",
        "电源与显示",
        ("shell", "dumpsys", "display"),
    ),
    QuickAdbCommand(
        "native_processes",
        "Native 服务进程",
        "快速查看 surfaceflinger、audioserver、cameraserver、media、netd、vold 等 Native 组件。",
        "native_service",
        "Native 服务",
        ("shell", "sh", "-c", 'ps -A | grep -E "surfaceflinger|audioserver|cameraserver|media|netd|vold"'),
    ),
    QuickAdbCommand(
        "native_surfaceflinger",
        "SurfaceFlinger",
        "查看合成、图层、显示管线和帧相关状态。",
        "native_service",
        "图形与媒体",
        ("shell", "dumpsys", "SurfaceFlinger"),
        timeout_seconds=25,
    ),
    QuickAdbCommand(
        "native_camera",
        "Camera Service",
        "查看 camera provider、设备枚举、客户端和错误状态。",
        "native_service",
        "图形与媒体",
        ("shell", "dumpsys", "media.camera"),
    ),
    QuickAdbCommand(
        "native_audio",
        "Audio Service",
        "查看音频路由、焦点、策略和 native audio 状态。",
        "native_service",
        "图形与媒体",
        ("shell", "dumpsys", "audio"),
    ),
    QuickAdbCommand(
        "native_connectivity",
        "Connectivity",
        "查看网络、NetworkAgent、默认网络和连接策略。",
        "native_service",
        "网络与存储",
        ("shell", "dumpsys", "connectivity"),
    ),
    QuickAdbCommand(
        "kernel_meminfo",
        "Kernel 内存",
        "读取 /proc/meminfo，判断系统级内存压力。",
        "kernel",
        "procfs",
        ("shell", "cat", "/proc/meminfo"),
    ),
    QuickAdbCommand(
        "kernel_uptime",
        "Kernel Uptime",
        "读取 /proc/uptime，判断是否发生过重启或异常恢复。",
        "kernel",
        "procfs",
        ("shell", "cat", "/proc/uptime"),
    ),
    QuickAdbCommand(
        "kernel_dmesg",
        "dmesg",
        "查看内核日志；部分 user build 可能没有权限。",
        "kernel",
        "内核日志",
        ("shell", "dmesg"),
        timeout_seconds=15,
        risk="may_require_privilege",
    ),
    QuickAdbCommand(
        "kernel_pstore_list",
        "pstore 列表",
        "查看是否存在 ramoops/console-ramoops 崩溃保留日志。",
        "kernel",
        "pstore",
        ("shell", "ls", "/sys/fs/pstore"),
        risk="may_require_privilege",
    ),
    QuickAdbCommand(
        "kernel_pstore_console",
        "console-ramoops",
        "读取 pstore console-ramoops；无文件或无权限时会返回错误。",
        "kernel",
        "pstore",
        ("shell", "sh", "-c", "cat /sys/fs/pstore/console-ramoops*"),
        timeout_seconds=15,
        risk="may_require_privilege",
    ),
    QuickAdbCommand(
        "bootreason_ro",
        "ro.boot.bootreason",
        "查看 bootloader/kernel 传入的启动原因。",
        "hardware",
        "启动原因",
        ("shell", "getprop", "ro.boot.bootreason"),
    ),
    QuickAdbCommand(
        "bootreason_sys",
        "sys.boot.reason",
        "查看 Android 记录的系统启动原因。",
        "hardware",
        "启动原因",
        ("shell", "getprop", "sys.boot.reason"),
    ),
    QuickAdbCommand(
        "logs_all_threadtime",
        "Logcat 快照",
        "抓取所有 buffer 的 threadtime 日志快照；使用 -d 一次性导出，避免持续阻塞。",
        "framework",
        "日志与证据",
        ("logcat", "-d", "-b", "all", "-v", "threadtime"),
        timeout_seconds=30,
    ),
    QuickAdbCommand(
        "bugreport_zip",
        "Bugreport ZIP",
        "生成完整 bugreport zip，文件落到 runtime/quick_adb。",
        "framework",
        "日志与证据",
        ("bugreport", "{bugreport_path}"),
        params=("bugreport_path",),
        timeout_seconds=180,
        risk="slow",
    ),
)


def quick_adb_command_by_id(command_id: str) -> QuickAdbCommand | None:
    for command in QUICK_ADB_COMMANDS:
        if command.command_id == command_id:
            return command
    return None

