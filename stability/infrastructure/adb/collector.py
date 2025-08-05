"""ADB collector façade for device and baseline monitoring APIs.

The implementation is split across focused mixins so the collector stays
testable without keeping all monitoring and device logic in one file.
"""

import logging
from collections import defaultdict
from typing import Any, Dict

from .app_metrics import AppMetricsMixin
from .cache import EnhancedCache
from .command_runner import ADBCommandMixin, BatchADBExecutor
from .device_info import DeviceInfoMixin
from .fps import FPSMetricsMixin
from .network import NetworkMetricsMixin
from .patterns import RegexPatternMixin
from .power import PowerMetricsMixin
from .system_metrics import SystemMetricsMixin
from .parsers.top import TopParserMixin

logger = logging.getLogger(__name__)

class ADBCollector(
    ADBCommandMixin,
    RegexPatternMixin,
    DeviceInfoMixin,
    SystemMetricsMixin,
    NetworkMetricsMixin,
    AppMetricsMixin,
    FPSMetricsMixin,
    PowerMetricsMixin,
    TopParserMixin,
):
    def __init__(self, timeout: int = 5, retry_count: int = 1):
        # Optimized timeout settings for better performance vs reliability balance
        self.timeout = timeout
        self.retry_count = retry_count
        self._device_id = None
        self._last_network_stats = {}

        # Enhanced multi-level cache system
        self.enhanced_cache = EnhancedCache()
        self._uid_cache = {}  # UID缓存，较长TTL
        self._compiled_patterns = {}  # 预编译正则表达式

        # Basic cache system for ADB commands
        self._cache = {}  # 基础命令缓存
        self._cache_timeout = 30.0  # 缓存超时时间（秒）

        # Performance tracking and optimization
        self._command_times = {}
        self._slow_commands = set()
        self._performance_stats = defaultdict(float)

        # Batch executor for parallel ADB commands
        self.batch_executor = BatchADBExecutor(self._device_id, max_workers=8)

        # Initialize compiled regex patterns
        self._init_regex_patterns()

        # Optimize data collection intervals based on data type
        self._collection_intervals = {
            'system_performance': 3.0,  # 系统性能每3秒采集
            'app_basic': 2.0,           # 应用基础信息每2秒
            'app_detailed': 5.0,        # 应用详细信息每5秒
            'network_stats': 4.0,       # 网络统计每4秒
            'device_info': 60.0         # 设备信息每分钟
        }
        self._last_collection_time = defaultdict(float)

    @property
    def device_id(self):
        """Get the current device ID"""
        return self._device_id

    @device_id.setter
    def device_id(self, value):
        """Set device ID and reinitialize batch executor"""
        self._device_id = value
        # Recreate batch executor with new device ID
        self.batch_executor = BatchADBExecutor(self._device_id, max_workers=8)


__all__ = [
    "ADBCollector",
    "EnhancedCache",
    "BatchADBExecutor",
]
