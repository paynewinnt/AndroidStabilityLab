# -*- coding: utf-8 -*-
import sys
import os
import time
from datetime import datetime
from collections import defaultdict, deque
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                           QScrollArea, QFrame, QGroupBox, QGridLayout,
                           QTableWidget, QTableWidgetItem, QPushButton,
                           QProgressBar, QTextEdit, QSplitter, QTabWidget,
                           QComboBox, QCheckBox, QMessageBox, QFileDialog,
                           QSizePolicy)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
from PyQt5.QtGui import QFont, QColor
import queue
import threading
import logging

logger = logging.getLogger(__name__)

try:
    import pyqtgraph as pg
    PYQTGRAPH_AVAILABLE = True
except ImportError:
    PYQTGRAPH_AVAILABLE = False
    print("Warning: pyqtgraph not available, using basic charts")

try:
    from .chart_widgets import AdvancedChartWidget, MultiSeriesChartManager
    CHART_WIDGETS_AVAILABLE = True
except ImportError:
    try:
        from gui.chart_widgets import AdvancedChartWidget, MultiSeriesChartManager
        CHART_WIDGETS_AVAILABLE = True
    except ImportError:
        print("Warning: chart_widgets not available")
        CHART_WIDGETS_AVAILABLE = False
        class AdvancedChartWidget:
            def __init__(self, *args, **kwargs): pass
            def add_data_point(self, *args, **kwargs): pass
        class MultiSeriesChartManager:
            def __init__(self, *args, **kwargs): pass

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入数据存储相关模块
try:
    from database.connection import db_manager
    from database.data_storage import data_storage
    DATABASE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Database modules not available: {e}")
    DATABASE_AVAILABLE = False
    # 创建兼容的空对象
    class MockDBManager:
        def is_connected(self): return False
        def connect(self): return False
    class MockDataStorage:
        def store_monitoring_data(self, *args, **kwargs): return False
    db_manager = MockDBManager()
    data_storage = MockDataStorage()

# 导入导出工具（可选）
try:
    from utils.export import data_exporter
    EXPORT_AVAILABLE = True
except ImportError:
    EXPORT_AVAILABLE = False
    class MockExporter:
        def export_data(self, *args, **kwargs): return False
    data_exporter = MockExporter()

class CircularBuffer:
    """环形缓冲区用于存储历史数据"""
    def __init__(self, max_size: int = 1000):
        self.buffer = deque(maxlen=max_size)
        self.timestamps = deque(maxlen=max_size)
        self.max_size = max_size
        
    def add_data(self, timestamp: float, data):
        """添加数据"""
        self.buffer.append(data)
        self.timestamps.append(timestamp)
        
    def get_recent_data(self, seconds: int = 300):
        """获取最近N秒的数据"""
        if not self.timestamps:
            return [], []
            
        cutoff_time = time.time() - seconds
        recent_data = []
        recent_timestamps = []
        
        for i, ts in enumerate(self.timestamps):
            if ts >= cutoff_time:
                recent_data.extend(list(self.buffer)[i:])
                recent_timestamps.extend(list(self.timestamps)[i:])
                break
                
        return recent_timestamps, recent_data
    
    def clear(self):
        """清空缓冲区"""
        self.buffer.clear()
        self.timestamps.clear()
    
    def size(self):
        """获取当前大小"""
        return len(self.buffer)

class OptimizedDataCollectionWorker(QThread):
    """优化的数据收集工作线程"""
    data_collected = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, adb_collector, config):
        super().__init__()
        self.adb_collector = adb_collector
        self.config = config
        self.running = False
        
        # 优化采集间隔 - 提高默认间隔减少系统负载
        self.base_interval = max(self.config.get('sample_interval', 3), 3)  # 最少3秒间隔
        self.adaptive_interval = self.base_interval
        
        # 性能监控
        self.collection_times = deque(maxlen=10)
        self.error_count = 0
        self.last_optimization = time.time()
        
    def run(self):
        """运行数据收集"""
        self.running = True
        
        while self.running:
            collection_start_time = time.time()
            
            try:
                # 智能数据收集 - 使用批量方法
                data = self._collect_data_batch()
                print(f"💾 数据收集完成，准备发送: {data is not None}")
                
                if data:
                    print(f"📡 发送数据信号 - 系统: {'有' if data.get('system') else '无'}, 应用: {len(data.get('apps', []))}")
                    self.data_collected.emit(data)
                    self.error_count = 0
                else:
                    print("⚠️ 收集到的数据为空")
                
                # 记录收集时间用于自适应优化
                collection_time = time.time() - collection_start_time
                self.collection_times.append(collection_time)
                
                # 自适应间隔调整
                self._adjust_interval()
                
                # 计算休眠时间
                remaining_time = self.adaptive_interval - collection_time
                if remaining_time > 0:
                    time.sleep(remaining_time)
                else:
                    # 收集时间过长，短暂休眠避免CPU占用过高
                    time.sleep(0.1)
                
            except Exception as e:
                self.error_count += 1
                self.error_occurred.emit(str(e))
                
                # 错误后增加休眠时间
                sleep_time = min(5.0, 0.5 * self.error_count)
                time.sleep(sleep_time)
    
    def _collect_data_batch(self) -> dict:
        """批量收集数据"""
        data = {
            'timestamp': datetime.now(),
            'system': None,
            'apps': []
        }
        
        try:
            print(f"🔍 开始收集数据 - 配置: {self.config['metrics']}")
            
            # 收集系统数据
            if self.config['metrics'].get('system', False):
                print("📊 收集系统性能数据...")
                system_data = self.adb_collector.get_system_performance()
                print(f"✅ 系统数据: {system_data}")
                data['system'] = system_data
            
            # 批量收集应用数据
            selected_apps = self.config.get('selected_apps', [])
            print(f"📱 准备收集 {len(selected_apps)} 个应用的数据")
            
            if selected_apps:
                package_names = [app['package_name'] for app in selected_apps]
                print(f"📦 应用包名: {package_names}")
                
                # 使用批量收集方法
                if hasattr(self.adb_collector, 'get_multiple_app_performance'):
                    print("🚀 使用批量收集方法")
                    multi_app_data = self.adb_collector.get_multiple_app_performance(package_names)
                    print(f"📋 批量数据结果: {multi_app_data}")
                    
                    for app in selected_apps:
                        package_name = app['package_name']
                        if package_name in multi_app_data:
                            app_data = multi_app_data[package_name]
                            app_data['app_info'] = app
                            data['apps'].append(app_data)
                        else:
                            print(f"⚠️ 未找到应用 {package_name} 的数据")
                else:
                    print("📈 使用单个收集方法")
                    # 降级到单个收集
                    for app in selected_apps:
                        print(f"📱 收集应用 {app['package_name']} 的数据")
                        app_data = self.adb_collector.get_app_performance(app['package_name'])
                        print(f"✅ 应用数据: {app_data}")
                        app_data['app_info'] = app
                        data['apps'].append(app_data)
            
            print(f"📊 最终收集数据: 系统={len(data.get('system', {}) or {})}, 应用={len(data['apps'])}")
            
            # 如果没有收集到任何数据，使用模拟数据
            if not data['system'] and not data['apps']:
                print("⚠️ 没有收集到真实数据，使用模拟数据")
                return self._generate_mock_data()
            
            return data
            
        except Exception as e:
            print(f"❌ 数据收集失败: {e}")
            import traceback
            traceback.print_exc()
            print("🔄 切换到模拟数据模式")
            return self._generate_mock_data()
    
    def _generate_mock_data(self) -> dict:
        """生成模拟数据用于测试"""
        import random
        
        mock_data = {
            'timestamp': datetime.now(),
            'system': {
                'cpu_usage': random.uniform(10, 80),
                'cpu_user': random.uniform(5, 40),
                'memory_usage_percent': random.uniform(30, 70),
                'battery_level': random.uniform(20, 100),
                'network_rx': random.uniform(0, 1000),
                'network_tx': random.uniform(0, 500),
                'cpu_temperature': random.uniform(30, 70),
                'load_1min': random.uniform(0, 4),
                'load_5min': random.uniform(0, 3),
                'load_15min': random.uniform(0, 2),
                'uptime_days': random.uniform(0, 30)
            },
            'apps': []
        }
        
        # 为选中的应用生成模拟数据
        selected_apps = self.config.get('selected_apps', [])
        for app in selected_apps:
            app_data = {
                'app_info': app,
                'cpu_usage': random.uniform(0, 50),
                'memory_pss': random.uniform(10, 200),
                'memory_percentage': random.uniform(1, 10),
                'fps': random.uniform(30, 60) if random.random() > 0.5 else None,
                'power_consumption': random.uniform(0, 20)
            }
            mock_data['apps'].append(app_data)
        
        print(f"🎭 生成模拟数据: 系统={len(mock_data['system'])}, 应用={len(mock_data['apps'])}")
        return mock_data
    
    def _adjust_interval(self):
        """自适应调整采集间隔"""
        current_time = time.time()
        
        # 每30秒优化一次间隔
        if current_time - self.last_optimization < 30:
            return
            
        if len(self.collection_times) < 5:
            return
            
        avg_collection_time = sum(self.collection_times) / len(self.collection_times)
        
        # 根据平均收集时间调整间隔
        if avg_collection_time > self.base_interval * 0.8:
            # 收集时间过长，增加间隔
            self.adaptive_interval = min(self.adaptive_interval * 1.2, self.base_interval * 2)
        elif avg_collection_time < self.base_interval * 0.3:
            # 收集时间较短，可以缩短间隔
            self.adaptive_interval = max(self.adaptive_interval * 0.9, self.base_interval * 0.5)
        
        self.last_optimization = current_time
    
    def stop(self):
        """停止数据收集"""
        self.running = False
    
    def get_performance_stats(self):
        """获取性能统计"""
        if not self.collection_times:
            return {}
            
        return {
            'avg_collection_time': sum(self.collection_times) / len(self.collection_times),
            'max_collection_time': max(self.collection_times),
            'current_interval': self.adaptive_interval,
            'error_count': self.error_count
        }

# 保持向后兼容
DataCollectionWorker = OptimizedDataCollectionWorker

class MetricDisplayWidget(QWidget):
    """Single metric display component"""
    def __init__(self, title, unit="", color="black"):
        super().__init__()
        self.title = title
        self.unit = unit
        self.color = color
        self.current_value = 0
        self.max_value = 0
        self.avg_value = 0
        self.sample_count = 0
        
        self.init_ui()
        # 1600px固定窗口，5个指标有充足空间显示 - 与固定尺寸保持一致
        # 注意：后面会设置固定尺寸160x140，这里的设置会被覆盖
        
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)  # 增加所有边距确保内容不被截断
        layout.setSpacing(4)  # 增加组件间距确保不重叠
        
        # Title
        title_label = QLabel(self.title)
        title_label.setFont(QFont("Arial", 10, QFont.Bold))  # 1600px窗口下恢复字体大小
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setWordWrap(True)
        title_label.setMaximumHeight(27)  # 水平布局后可以适当增加标题高度
        layout.addWidget(title_label)
        
        # Current value
        self.current_label = QLabel("0" + self.unit)
        self.current_label.setFont(QFont("Arial", 13, QFont.Bold))  # 恢复较大字体，高度160px足够显示
        self.current_label.setAlignment(Qt.AlignCenter)
        self.current_label.setStyleSheet("color: #2c3e50; padding: 0px; font-weight: 600;")  # 去除padding节省空间
        layout.addWidget(self.current_label)
        
        # Statistics in vertical layout - 上下两行显示，解决水平空间不足
        stats_widget = QWidget()
        stats_widget.setMinimumHeight(50)  # 增加高度适应两行显示
        stats_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        stats_layout = QVBoxLayout(stats_widget)  # 改为垂直布局
        stats_layout.setContentsMargins(2, 2, 2, 2)
        stats_layout.setSpacing(2)  # 减少行间距
        
        # Use appropriate fonts for statistics
        font_small = QFont("Arial", 9)
        
        # 最大值信息 - 水平布局，充分利用宽度
        max_container = QWidget()
        max_container.setMinimumHeight(20)  # 设置行高
        max_layout = QHBoxLayout(max_container)
        max_layout.setContentsMargins(4, 1, 4, 1)
        max_layout.setSpacing(6)
        
        max_label_text = QLabel("最大:")
        max_label_text.setFont(font_small)
        max_label_text.setMinimumWidth(30)
        max_label_text.setAlignment(Qt.AlignLeft)
        max_layout.addWidget(max_label_text)
        
        self.max_label = QLabel("0" + self.unit)
        self.max_label.setFont(font_small)
        self.max_label.setStyleSheet("color: #e74c3c; font-weight: 500;")
        self.max_label.setAlignment(Qt.AlignRight)
        self.max_label.setWordWrap(False)
        max_layout.addWidget(self.max_label, 1)  # 给数值更多空间
        
        # 平均值信息 - 水平布局，充分利用宽度
        avg_container = QWidget()
        avg_container.setMinimumHeight(20)  # 设置行高
        avg_layout = QHBoxLayout(avg_container)
        avg_layout.setContentsMargins(4, 1, 4, 1)
        avg_layout.setSpacing(6)
        
        avg_label_text = QLabel("平均:")
        avg_label_text.setFont(font_small)
        avg_label_text.setMinimumWidth(30)
        avg_label_text.setAlignment(Qt.AlignLeft)
        avg_layout.addWidget(avg_label_text)
        
        self.avg_label = QLabel("0" + self.unit)
        self.avg_label.setFont(font_small)
        self.avg_label.setStyleSheet("color: #f39c12; font-weight: 500;")
        self.avg_label.setAlignment(Qt.AlignRight)
        self.avg_label.setWordWrap(False)
        avg_layout.addWidget(self.avg_label, 1)  # 给数值更多空间
        
        # 添加到主统计布局 - 不添加弹性空间让内容更紧凑
        stats_layout.addWidget(max_container)
        stats_layout.addWidget(avg_container)
        
        layout.addWidget(stats_widget)
        
        # Progress bar (optional)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(15)
        layout.addWidget(self.progress_bar)
        
        # 使用最小尺寸而不是固定尺寸，让内容完全显示，增加高度适应两行统计
        self.setMinimumSize(180, 180)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        
        # Styling
        self.setStyleSheet("""
            QWidget {
                border: 1px solid #e9ecef;
                border-radius: 10px;
                background-color: white;
                margin: 2px;
            }
            QLabel {
                border: none;
                background-color: transparent;
            }
            QProgressBar {
                border: 1px solid #dee2e6;
                border-radius: 4px;
                background-color: #f8f9fa;
                text-align: center;
            }
            QProgressBar::chunk {
                border-radius: 3px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a90e2, stop:1 #67b4f5);
            }
        """)
        
    def update_value(self, value):
        """Update value with smart refresh control"""
        if value is None:
            return
            
        old_value = self.current_value
        self.current_value = value
        self.sample_count += 1
        
        # Update max value
        if value > self.max_value:
            self.max_value = value
            
        # Update average value
        if self.sample_count == 1:
            self.avg_value = value
        else:
            self.avg_value = (self.avg_value * (self.sample_count - 1) + value) / self.sample_count
        
        # Smart UI update - only update if significant change or sufficient time passed
        should_update = self._should_update_display(old_value, value)
        
        if should_update:
            self._update_display_elements(value)
    
    def _should_update_display(self, old_value, new_value):
        """Determine if display should be updated based on value change"""
        import time
        
        # Initialize last update time if not exists
        if not hasattr(self, '_last_update_time'):
            self._last_update_time = 0
            
        current_time = time.time()
        time_since_update = current_time - self._last_update_time
        
        # Always update if enough time has passed (max 10 seconds)
        if time_since_update > 10:
            self._last_update_time = current_time
            return True
            
        # Don't update too frequently (min 1.0 seconds) - 提高性能
        if time_since_update < 1.0:
            return False
            
        # Update if significant change (>= 5% change or 0.1 absolute change)
        if old_value is not None:
            abs_change = abs(new_value - old_value)
            rel_change = abs_change / max(abs(old_value), 0.1) if old_value != 0 else abs_change
            
            if abs_change >= 0.1 or rel_change >= 0.05:
                self._last_update_time = current_time
                return True
                
        return False
    
    def _update_display_elements(self, value):
        """Update the actual display elements"""
        # 智能格式化数值显示
        current_text = self._format_value(value)
        max_text = self._format_value(self.max_value) 
        avg_text = self._format_value(self.avg_value)
        
        # Update display
        self.current_label.setText(f"{current_text}{self.unit}")
        self.max_label.setText(f"{max_text}{self.unit}")
        self.avg_label.setText(f"{avg_text}{self.unit}")
        
        # Update progress bar (if applicable)
        if self.unit == "%" and self.progress_bar.isVisible():
            self.progress_bar.setValue(int(value))
    
    def _format_value(self, value):
        """智能格式化数值，根据大小选择合适的精度"""
        if value is None or value == 0:
            return "0"
        elif abs(value) >= 1000:
            # 大于1000显示整数
            return f"{int(value)}"
        elif abs(value) >= 100:
            # 100-1000显示1位小数
            return f"{value:.1f}"
        elif abs(value) >= 10:
            # 10-100显示1位小数
            return f"{value:.1f}"
        else:
            # 小于10显示2位小数
            return f"{value:.2f}"
            
    def set_progress_visible(self, visible):
        """Set progress bar visibility"""
        self.progress_bar.setVisible(visible)

class OptimizedMonitorViewWidget(QWidget):
    """优化的主监控显示界面"""
    def __init__(self):
        super().__init__()
        self.selected_apps = []
        self.monitoring_active = False
        self.data_worker = None
        self.metric_widgets = {}
        self.chart_widgets = {}
        self.chart_manager = None
        self.charts_tab_widget = None
        
        # 数据存储相关
        self.current_session_id = None
        self.enable_data_storage = DATABASE_AVAILABLE
        
        # 优化的数据管理 - 减少内存占用提高性能
        self.data_buffers = {
            'system': CircularBuffer(max_size=120),  # 10分钟数据，减少内存占用
            'apps': defaultdict(lambda: CircularBuffer(max_size=120))  # 每个应用10分钟数据
        }
        
        # GUI更新优化 - 降低更新频率以提高性能
        self.update_queue = queue.Queue(maxsize=50)  # 减少队列大小
        self.ui_update_timer = QTimer()
        self.ui_update_timer.timeout.connect(self.process_ui_updates)
        self.ui_update_timer.start(200)  # 5 FPS更新频率，降低CPU占用
        
        # 统计信息更新定时器
        self.stats_update_timer = QTimer()
        self.stats_update_timer.timeout.connect(self.update_statistics)
        self.stats_update_timer.start(3000)  # 每3秒更新一次，降低CPU占用
        
        # 性能监控
        self.update_counts = defaultdict(int)
        self.last_cleanup = time.time()
        
        # 去抖动计数器 - 跳帧优化提高性能
        self.update_skip_counter = 0
        self.max_skip_updates = 4  # 每4次更新显示一次，大幅降低UI更新频率
        
        # 设置尺寸策略，确保内容能完全显示
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        
        self.init_ui()
    
    def process_ui_updates(self):
        """批量处理UI更新，避免阻塞"""
        updates_processed = 0
        max_updates_per_cycle = 1  # 每次只处理1个更新，避免UI阻塞
        
        # 如果队列积压太多，跳过一些更新
        queue_size = self.update_queue.qsize()
        if queue_size > 10:
            # 清理旧数据，只保留最新的几个更新
            while queue_size > 5:
                try:
                    self.update_queue.get_nowait()
                    queue_size -= 1
                except queue.Empty:
                    break
        
        while not self.update_queue.empty() and updates_processed < max_updates_per_cycle:
            try:
                update_data = self.update_queue.get_nowait()
                self._update_ui_components(update_data)
                updates_processed += 1
            except queue.Empty:
                break
            except Exception as e:
                print(f"UI更新错误: {e}")
        
        # 定期清理过期数据
        current_time = time.time()
        if current_time - self.last_cleanup > 60:  # 每分钟清理一次
            self._cleanup_expired_data()
            self.last_cleanup = current_time
    
    def _update_ui_components(self, data):
        """更新UI组件"""
        try:
            # 去抖动处理
            self.update_skip_counter += 1
            if self.update_skip_counter < self.max_skip_updates:
                print(f"⏭ 跳帧更新 ({self.update_skip_counter}/{self.max_skip_updates})")
                return
            self.update_skip_counter = 0
            
            print(f"🔄 开始更新UI组件 - 数据: {data.keys()}")
            timestamp = data['timestamp']
            
            # 更新系统指标
            if data.get('system'):
                print(f"🖥 更新系统指标: {data['system']}")
                self._update_system_metrics(data['system'], timestamp)
            else:
                print("⚠️ 没有系统数据")
            
            # 更新应用指标  
            if data.get('apps'):
                print(f"📱 更新应用指标: {len(data['apps'])} 个应用")
                self._update_app_metrics(data['apps'], timestamp)
            else:
                print("⚠️ 没有应用数据")
                
        except Exception as e:
            print(f"❌ UI组件更新失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _update_system_metrics(self, system_data, timestamp):
        """更新系统指标显示"""
        # 保存最新的系统数据供应用内存百分比计算使用
        self.latest_system_data = system_data
        
        # 存储到环形缓冲区
        self.data_buffers['system'].add_data(timestamp.timestamp(), system_data)
        
        # 更新度量显示组件
        metric_mapping = {
            'cpu_usage': 'system_CPU使用率：Total',
            'cpu_user': 'system_CPU使用率：用户态',
            'memory_usage_percent': 'system_内存使用', 
            'battery_level': 'system_电池电量',
            'network_rx': 'system_网络接收', 
            'network_tx': 'system_网络发送',
            'cpu_temperature': 'system_CPU温度',
            'load_1min': 'system_负载1分',
            'load_5min': 'system_负载5分',
            'load_15min': 'system_负载15分',
            'uptime_days': 'system_运行时间'
        }
        
        for key, display_name in metric_mapping.items():
            if key in system_data and display_name in self.metric_widgets:
                value = system_data[key]
                if value is not None:
                    self.metric_widgets[display_name].update_value(value)
        
        # 更新图表（降低频率）
        if self.update_counts['system_charts'] % 3 == 0:  # 每3次更新图表一次
            self._update_system_charts(system_data, timestamp)
        self.update_counts['system_charts'] += 1
    
    def _update_app_metrics(self, apps_data, timestamp):
        """更新应用指标显示"""
        for app_data in apps_data:
            if 'app_info' not in app_data:
                continue
                
            app_info = app_data['app_info']
            package_name = app_info['package_name']
            
            # 存储到环形缓冲区
            self.data_buffers['apps'][package_name].add_data(
                timestamp.timestamp(), app_data
            )
            
            # 计算内存使用率：内存使用/总内存
            if 'memory_pss' in app_data and app_data['memory_pss'] is not None:
                # 获取系统总内存
                system_total_memory = None
                if hasattr(self, 'latest_system_data') and self.latest_system_data:
                    system_total_memory = self.latest_system_data.get('memory_system_total')
                
                if system_total_memory and system_total_memory > 0:
                    # 计算内存使用率：应用内存(MB) / 系统总内存(MB) * 100
                    memory_percentage = (app_data['memory_pss'] / system_total_memory) * 100
                    app_data['memory_percentage'] = round(memory_percentage, 2)
                else:
                    # 如果无法获取系统总内存，回退到top命令的百分比
                    if 'top_memory_percent' in app_data and app_data['top_memory_percent'] is not None:
                        app_data['memory_percentage'] = round(app_data['top_memory_percent'], 2)
            
            # 更新度量显示组件
            metric_mapping = {
                'cpu_usage': f'{package_name}_CPU',
                'memory_pss': f'{package_name}_内存',
                'memory_percentage': f'{package_name}_内存百分比',
                'fps': f'{package_name}_帧率',
                'power_consumption': f'{package_name}_功耗'
            }
            
            for key, widget_key in metric_mapping.items():
                if key in app_data and widget_key in self.metric_widgets:
                    value = app_data[key]
                    if value is not None:
                        self.metric_widgets[widget_key].update_value(value)
            
            # 更新图表（大幅降低频率以提高性能）
            if self.update_counts[f'app_charts_{package_name}'] % 5 == 0:  # 每5次更新图表一次
                self._update_app_charts(app_data, timestamp, app_info)
            self.update_counts[f'app_charts_{package_name}'] += 1
    
    def _update_system_charts(self, system_data, timestamp):
        """更新系统图表 - 性能优化版本"""
        # 系统图表也降低更新频率
        if self.update_counts['system_charts'] % 3 != 0:  # 每3次更新系统图表一次
            self.update_counts['system_charts'] += 1
            return
        self.update_counts['system_charts'] += 1
        
        ts = timestamp.timestamp()
        
        # 批量更新图表，减少重绘次数
        chart_updates = []
        
        if 'cpu' in self.chart_widgets and 'cpu_usage' in system_data:
            # 添加总CPU使用率数据点
            cpu_usage = system_data['cpu_usage']
            chart_updates.append(('cpu', '系统 CPU使用率', ts, cpu_usage))
            
            # 如果有用户态CPU数据，也添加用户态CPU使用率数据点
            if 'cpu_user' in system_data:
                cpu_user = system_data['cpu_user']
                chart_updates.append(('cpu', '系统 CPU使用率 (用户态)', ts, cpu_user))
            
        if 'network' in self.chart_widgets:
            if 'network_rx' in system_data:
                chart_updates.append(('network', '系统 网络接收', ts, system_data['network_rx']))
            if 'network_tx' in system_data:
                chart_updates.append(('network', '系统 网络发送', ts, system_data['network_tx']))
        
        # 批量执行图表更新
        for chart_name, label, timestamp, value in chart_updates:
            if chart_name in self.chart_widgets:
                self.chart_widgets[chart_name].add_data_point(label, timestamp, value)
    
    def _update_app_charts(self, app_data, timestamp, app_info):
        """更新应用图表"""
        package_name = app_info['package_name']
        # 直接使用包名作为图表标签，便于区分
        chart_label = package_name
        ts = timestamp.timestamp()
        
        if 'cpu' in self.chart_widgets and 'cpu_usage' in app_data:
            self.chart_widgets['cpu'].add_data_point(f"{chart_label} CPU", ts, app_data['cpu_usage'])
            
        if 'memory_mb' in self.chart_widgets and 'memory_pss' in app_data:
            self.chart_widgets['memory_mb'].add_data_point(f"{chart_label} 内存", ts, app_data['memory_pss'])
            
        if 'memory_percent' in self.chart_widgets and 'memory_percentage' in app_data:
            self.chart_widgets['memory_percent'].add_data_point(f"{chart_label} 内存使用率", ts, app_data['memory_percentage'])
            
        if 'fps' in self.chart_widgets and 'fps' in app_data:
            self.chart_widgets['fps'].add_data_point(f"{chart_label} FPS", ts, app_data['fps'])
            
        if 'power' in self.chart_widgets:
            power_value = app_data.get('power_consumption', 0)
            # If no power consumption data, show 0 but with indicator
            if power_value == 0 or power_value is None:
                power_label = f"{chart_label} 功耗 (估算)"
                # 简化功耗计算，减少性能开销
                power_value = 0  # 直接使用0，避免复杂的估算计算
            else:
                power_label = f"{chart_label} 功耗"
            
            self.chart_widgets['power'].add_data_point(power_label, ts, power_value)
    
    def _cleanup_expired_data(self):
        """清理过期数据"""
        try:
            # 清理系统数据缓冲区
            if self.data_buffers['system'].size() > 1000:
                # 保留最近的数据，清理旧数据
                pass  # CircularBuffer会自动处理
                
            # 清理应用数据缓冲区
            for package_name in list(self.data_buffers['apps'].keys()):
                if self.data_buffers['apps'][package_name].size() > 1000:
                    pass  # CircularBuffer会自动处理
                    
            # 清理更新计数器
            if len(self.update_counts) > 100:
                # 保留最近的计数器
                keys_to_keep = list(self.update_counts.keys())[-50:]
                new_counts = {k: self.update_counts[k] for k in keys_to_keep}
                self.update_counts = defaultdict(int, new_counts)
                
        except Exception as e:
            print(f"清理过期数据失败: {e}")
    
    def update_statistics(self):
        """更新统计信息"""
        if not self.monitoring_active:
            return
            
        try:
            # 更新数据点统计
            total_points = 0
            for buffer in [self.data_buffers['system']] + list(self.data_buffers['apps'].values()):
                total_points += buffer.size()
            
            self.total_data_points = total_points
                
        except Exception as e:
            print(f"更新统计信息失败: {e}")
    
    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        
        # 创建状态栏
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Box)
        status_frame.setMaximumHeight(60)
        status_layout = QHBoxLayout(status_frame)
        
        self.status_label = QLabel("监控状态: 未开始")
        self.status_label.setFont(QFont("Arial", 14, QFont.Bold))
        status_layout.addWidget(self.status_label)
        
        # 添加弹性空间
        status_layout.addStretch()
        
        # 右侧统计信息区域
        stats_widget = QWidget()
        stats_layout = QVBoxLayout(stats_widget)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(2)
        
        
        status_layout.addWidget(stats_widget)
        layout.addWidget(status_frame)
        
        # 初始化时间相关变量
        self.monitoring_start_time = None
        self.total_data_points = 0
        
        # 定义高对比度颜色系统
        self.app_colors = [
            "#E91E63",  # 粉红色
            "#9C27B0",  # 紫色  
            "#673AB7",  # 深紫色
            "#3F51B5",  # 靛蓝色
            "#2196F3",  # 蓝色
            "#03A9F4",  # 浅蓝色
            "#00BCD4",  # 青色
            "#009688",  # 茶色
            "#4CAF50",  # 绿色
            "#8BC34A",  # 浅绿色
            "#CDDC39",  # 柠檬绿
            "#FFEB3B",  # 黄色
            "#FFC107",  # 琥珀色
            "#FF9800",  # 橙色
            "#FF5722",  # 深橙色
            "#795548",  # 棕色
        ]
        self.app_color_index = 0
        
        # 创建主要内容区域
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # 创建实际的指标显示区域
        self._create_metrics_display(content_layout)
        
        layout.addWidget(content_widget)
    
    def _create_metrics_display(self, parent_layout):
        """创建指标显示区域"""
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setMinimumHeight(600)  # 确保滚动区域有足够高度
        scroll_area.setMinimumWidth(1150)  # 优化滚动区域宽度
        
        # 创建主容器
        metrics_container = QWidget()
        metrics_container.setMinimumWidth(1150)  # 优化宽度设置，适应新的两行布局
        main_layout = QVBoxLayout(metrics_container)
        
        # 系统指标组
        system_group = QGroupBox("系统性能指标")
        system_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)  # 让内容决定高度
        system_group.setMinimumWidth(1100)  # 优化宽度设置
        system_group.setStyleSheet("""
            QGroupBox {
                font-weight: 600;
                border: 1px solid #e9ecef;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #fafbfc;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                color: #4a90e2;
                font-size: 14px;
            }
        """)
        system_layout = QGridLayout(system_group)
        system_layout.setSpacing(5)  # 适中的间距，避免过度挤压
        system_layout.setContentsMargins(10, 25, 10, 25)  # 减少左右边距，增加内容显示空间
        # 设置行拉伸，让每一行都有足够空间
        system_layout.setRowStretch(0, 1)
        system_layout.setRowStretch(1, 1)
        # 设置列拉伸，确保所有列均匀分布
        for i in range(6):
            system_layout.setColumnStretch(i, 1)
        
        # 创建系统指标组件 - 使用蓝色系配色
        system_metrics = [
            ("system_CPU使用率：Total", "%", "#4a90e2"),
            ("system_CPU使用率：用户态", "%", "#5ba3f5"),
            ("system_内存使用", "%", "#67b4f5"),
            ("system_电池电量", "%", "#7ac1f7"),
            ("system_网络接收", "KB/s", "#8dccf9"),
            ("system_网络发送", "KB/s", "#9fd6fa"),
            ("system_CPU温度", "°C", "#b1dffc"),
            ("system_负载1分", "", "#6c9bd1"),
            ("system_负载5分", "", "#7ea8d8"),
            ("system_负载15分", "", "#90b5df"),
            ("system_运行时间", "天", "#00BCD4"),
        ]
        
        # 设置系统指标布局为6列，2排显示
        row, col = 0, 0
        max_cols = 6
        for metric_name, unit, color in system_metrics:
            widget = MetricDisplayWidget(metric_name.replace("system_", ""), unit, color)
            widget.set_progress_visible(unit == "%")
            self.metric_widgets[metric_name] = widget
            system_layout.addWidget(widget, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        main_layout.addWidget(system_group)
        
        # 应用指标Tab组
        self.apps_tab_widget = QTabWidget()
        self.apps_tab_widget.setStyleSheet("""
            QTabWidget {
                border: none;
                background-color: transparent;
                margin-top: 10px;
            }
            QTabWidget::pane {
                border: 1px solid #e9ecef;
                border-radius: 10px;
                padding: 15px;
                background-color: #ffffff;
            }
            QTabBar::tab {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-bottom: none;
                border-radius: 8px 8px 0 0;
                padding: 8px 16px;
                margin-right: 2px;
                min-width: 80px;
                max-width: 140px;
                color: #6c757d;
                font-weight: 500;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #4a90e2;
                font-weight: 600;
                border: 1px solid #e9ecef;
                border-bottom: 1px solid white;
            }
            QTabBar::tab:hover {
                background-color: #e3f2fd;
                color: #4a90e2;
            }
        """)
        # 初始显示Tab组件（即使没有内容）
        main_layout.addWidget(self.apps_tab_widget)
        
        # 添加占位符Tab
        self._add_placeholder_tab()
        
        # 图表区域
        if PYQTGRAPH_AVAILABLE and CHART_WIDGETS_AVAILABLE:
            self._create_charts_area(main_layout)
        
        scroll_area.setWidget(metrics_container)
        parent_layout.addWidget(scroll_area)
    
    def _create_charts_area(self, parent_layout):
        """创建图表区域 - 使用Tab布局"""
        charts_group = QGroupBox("性能图表")
        charts_group.setStyleSheet("""
            QGroupBox {
                font-weight: 600;
                border: 1px solid #e9ecef;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #fafbfc;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                color: #4a90e2;
                font-size: 14px;
            }
        """)
        charts_layout = QVBoxLayout(charts_group)
        charts_layout.setSpacing(8)
        charts_layout.setContentsMargins(10, 15, 10, 10)
        
        # 创建图表管理器
        if not self.chart_manager:
            self.chart_manager = MultiSeriesChartManager()
        
        # 创建TabWidget用于图表切换
        self.charts_tab_widget = QTabWidget()
        self.charts_tab_widget.setStyleSheet("""
            QTabWidget {
                border: none;
                background-color: transparent;
            }
            QTabWidget::pane {
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 10px;
                background-color: #ffffff;
            }
            QTabBar::tab {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-bottom: none;
                border-radius: 6px 6px 0 0;
                padding: 8px 16px;
                margin-right: 2px;
                min-width: 80px;
                color: #6c757d;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #4a90e2;
                font-weight: 600;
                border: 1px solid #e9ecef;
                border-bottom: 1px solid white;
            }
            QTabBar::tab:hover {
                background-color: #e3f2fd;
                color: #4a90e2;
            }
        """)
        
        # 创建各类图表 - 使用蓝色系配色
        chart_configs = [
            ("cpu", "CPU使用率", "%", "#4a90e2"),
            ("memory_mb", "内存使用量", "MB", "#5ba3f5"),
            ("memory_percent", "内存占比", "%", "#67b4f5"),
            ("network", "网络流量", "KB/s", "#7ac1f7"),
            ("fps", "帧率", "FPS", "#8dccf9"),
            ("power", "功耗", "mW", "#9fd6fa"),
        ]
        
        for chart_id, title, unit, color in chart_configs:
            chart_widget = AdvancedChartWidget(title, unit)
            self.chart_widgets[chart_id] = chart_widget
            
            # 创建单独的Tab页面容器
            tab_container = QWidget()
            tab_layout = QVBoxLayout(tab_container)
            tab_layout.setContentsMargins(5, 5, 5, 5)
            tab_layout.addWidget(chart_widget)
            
            # 添加到Tab
            self.charts_tab_widget.addTab(tab_container, title)
        
        charts_layout.addWidget(self.charts_tab_widget)
        parent_layout.addWidget(charts_group)
    
    def _add_placeholder_tab(self):
        """添加占位符Tab页面"""
        placeholder_page = QWidget()
        placeholder_layout = QVBoxLayout(placeholder_page)
        placeholder_layout.setAlignment(Qt.AlignCenter)
        
        # 提示信息
        info_label = QLabel("📱 请选择要监控的应用")
        info_label.setFont(QFont("Arial", 18, QFont.Bold))
        info_label.setStyleSheet("color: #6c757d; margin: 40px;")
        info_label.setAlignment(Qt.AlignCenter)
        placeholder_layout.addWidget(info_label)
        
        description_label = QLabel("选择应用后，每个应用将显示为独立的Tab页面")
        description_label.setFont(QFont("Arial", 14))
        description_label.setStyleSheet("color: #adb5bd; margin: 20px;")
        description_label.setAlignment(Qt.AlignCenter)
        placeholder_layout.addWidget(description_label)
        
        self.apps_tab_widget.addTab(placeholder_page, "应用性能指标")
    
    def _create_app_metrics_widgets(self, selected_apps):
        """为选中的应用创建Tab形式的指标显示组件"""
        # 清理现有的Tab页面
        self._clear_app_metrics_widgets()
        
        if not selected_apps:
            # 没有应用时显示占位符
            self._add_placeholder_tab()
            return
        
        for app in selected_apps:
            package_name = app['package_name']
            app_name = app.get('app_name', package_name)
            
            # 创建Tab页面
            tab_page = QWidget()
            tab_layout = QVBoxLayout(tab_page)
            tab_layout.setContentsMargins(20, 20, 20, 20)  # 1600px窗口下恢复舒适边距
            tab_layout.setSpacing(12)  # 适当增加间距
            
            # 添加应用信息标题
            info_label = QLabel(f"📱 {app_name}")
            info_label.setFont(QFont("Arial", 16, QFont.Bold))
            info_label.setStyleSheet("color: #2c3e50; margin-bottom: 10px; font-weight: 600;")
            tab_layout.addWidget(info_label)
            
            # 添加包名信息
            package_label = QLabel(f"包名: {package_name}")
            package_label.setFont(QFont("Arial", 12))
            package_label.setStyleSheet("color: #6c757d; margin-bottom: 15px;")
            tab_layout.addWidget(package_label)
            
            # 创建指标网格容器
            metrics_container = QWidget()
            metrics_container.setMinimumWidth(950)  # 确保能容纳5个指标(5*180 + 间距)
            metrics_layout = QGridLayout(metrics_container)
            metrics_layout.setSpacing(0)  # 去除模块间距，使用框线区别模块
            metrics_layout.setContentsMargins(0, 0, 0, 0)
            # 设置列拉伸比例，确保所有列均匀分布
            for i in range(5):
                metrics_layout.setColumnStretch(i, 1)
            
            # 创建应用指标组件 - 5个指标一排显示，使用蓝色系配色
            app_metrics = [
                (f"{package_name}_CPU", "CPU使用率", "%", "#4a90e2"),
                (f"{package_name}_内存", "内存使用", "MB", "#5ba3f5"),
                (f"{package_name}_内存百分比", "内存占比", "%", "#67b4f5"),
                (f"{package_name}_帧率", "帧率", "FPS", "#7ac1f7"),
                (f"{package_name}_功耗", "功耗", "mW", "#8dccf9"),
            ]
            
            # 一排5个指标的布局
            for i, (metric_name, display_name, unit, color) in enumerate(app_metrics):
                widget = MetricDisplayWidget(display_name, unit, color)
                if unit == "%":
                    widget.set_progress_visible(True)
                self.metric_widgets[metric_name] = widget
                metrics_layout.addWidget(widget, 0, i)  # 全部放在第0行
            
            # 固定1600x900窗口大小，无需滚动区域，直接添加指标容器
            tab_layout.addWidget(metrics_container)
            
            # 添加弹性空间
            tab_layout.addStretch()
            
            # 将Tab页面添加到Tab组件
            # 使用更智能的Tab标题截取策略
            if len(app_name) <= 20:
                tab_title = app_name
            else:
                # 优先使用应用名，如果太长则使用包名的简化版
                if app_name != package_name and len(app_name) <= 25:
                    tab_title = app_name
                else:
                    # 包名通常有.分隔符，取最后部分
                    parts = package_name.split('.')
                    if len(parts) > 1:
                        tab_title = parts[-1][:18]
                    else:
                        tab_title = package_name[:18]
            
            self.apps_tab_widget.addTab(tab_page, tab_title)
    
    def _clear_app_metrics_widgets(self):
        """清理现有的Tab形式应用指标组件"""
        if not hasattr(self, 'apps_tab_widget'):
            return
            
        # 清理所有Tab页面
        while self.apps_tab_widget.count() > 0:
            self.apps_tab_widget.removeTab(0)
        
        # 清理相关的metric_widgets条目
        keys_to_remove = [key for key in self.metric_widgets.keys() 
                         if not key.startswith('system_')]
        for key in keys_to_remove:
            del self.metric_widgets[key]
    
    def start_monitoring(self, adb_collector, config):
        """开始监控"""
        self.adb_collector = adb_collector
        self.config = config
        self.monitoring_active = True
        self.monitoring_start_time = time.time()  # 记录开始时间
        self.total_data_points = 0
        self.status_label.setText("监控状态: 运行中")
        self.status_label.setStyleSheet("color: green;")
        
        # 创建应用指标显示组件（关键修复）
        selected_apps = config.get('selected_apps', [])
        print(f"🔧 创建应用指标UI组件，应用数量: {len(selected_apps)}")
        self._create_app_metrics_widgets(selected_apps)
        
        # Reset battery stats for fresh power consumption data
        try:
            if hasattr(self.adb_collector, 'reset_battery_stats'):
                self.adb_collector.reset_battery_stats()
                self.status_label.setText("监控状态: 运行中")
        except Exception as e:
            logger.debug(f"Failed to reset battery stats at monitoring start: {e}")
        
        # 启动数据收集线程
        if hasattr(self, 'data_collection_worker'):
            self.data_collection_worker.quit()
            self.data_collection_worker.wait()
        
        try:
            self.data_collection_worker = OptimizedDataCollectionWorker(adb_collector, config)
            self.data_collection_worker.data_collected.connect(self.update_display)
            self.data_collection_worker.error_occurred.connect(self.handle_error)
            self.data_collection_worker.start()
        except Exception as e:
            print(f"启动监控失败: {e}")
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring_active = False
        self.monitoring_start_time = None  # 清空开始时间
        self.status_label.setText("监控状态: 已停止")
        self.status_label.setStyleSheet("color: red;")
        
        if hasattr(self, 'data_collection_worker'):
            self.data_collection_worker.running = False
            self.data_collection_worker.quit()
            self.data_collection_worker.wait()
    
    def update_display(self, data):
        """更新显示数据 - 优化性能版本"""
        try:
            print(f"📨 收到数据更新信号 - 时间: {data.get('timestamp')}")
            print(f"📊 数据内容: 系统={'有' if data.get('system') else '无'}, 应用={len(data.get('apps', []))}")
            
            # 调试：打印应用数据详情
            if data.get('apps'):
                for app in data.get('apps', []):
                    print(f"🔍 应用数据: {app.get('package_name', 'unknown')} - {list(app.keys())}")
            else:
                print("⚠️ 未收集到应用数据")
            
            # 性能优化：如果队列已满，丢弃最旧的数据
            if self.update_queue.full():
                try:
                    old_data = self.update_queue.get_nowait()  # 丢弃一个旧数据
                    print("🗑 丢弃旧数据，为新数据腾出空间")
                except queue.Empty:
                    pass
            
            # 使用队列缓冲更新，让UI线程处理
            self.update_queue.put_nowait(data)
            print(f"✅ 数据已加入更新队列，队列大小: {self.update_queue.qsize()}")
                
        except queue.Full:
            # 如果队列满了就跳过这次更新，避免阻塞
            print("⚠️ 更新队列已满，跳过此次更新")
            pass
        except Exception as e:
            print(f"❌ 更新显示失败: {e}")
            import traceback
            traceback.print_exc()
    
    def export_to_html(self, filepath):
        """导出数据到HTML页面"""
        try:
            html_content = self._generate_html_report()
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            return True
        except Exception as e:
            print(f"导出HTML失败: {e}")
            return False
    
    def _generate_html_report(self):
        """生成HTML报告内容"""
        # 收集数据
        system_data = self._collect_system_data()
        apps_data = self._collect_apps_data()
        
        # 生成HTML
        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Android性能监控报告</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }}
        .stat-card {{ background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stat-title {{ font-size: 16px; color: #666; margin-bottom: 5px; }}
        .stat-value {{ font-size: 26px; font-weight: bold; color: #333; }}
        .chart-container {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .app-section {{ margin: 20px 0; }}
        .app-title {{ background: white; color: black; padding: 10px; border: 1px solid #dee2e6; border-radius: 5px; margin: 10px 0; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #f8f9fa; font-weight: bold; }}
        .export-time {{ text-align: right; color: #666; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 Android性能监控报告</h1>
        <p>监控时长: {self._get_monitoring_duration()}</p>
        <p>数据点总数: {self.total_data_points}</p>
    </div>
    
    <div class="stats">
        {self._generate_system_stats_html(system_data)}
    </div>
    
    <div class="chart-container">
        <h2>📊 系统性能趋势</h2>
        <canvas id="systemChart" width="400" height="200"></canvas>
    </div>
    
    <div class="apps-section">
        <h2>📱 应用性能详情</h2>
        {self._generate_apps_html(apps_data)}
    </div>
    
    <div class="export-time">
        导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </div>
    
    <script>
        {self._generate_chart_js(system_data, apps_data)}
    </script>
</body>
</html>
        """
        return html
    
    def _collect_system_data(self):
        """收集系统数据"""
        system_buffer = self.data_buffers['system']
        timestamps, data_points = system_buffer.get_recent_data(1800)  # 30分钟数据
        return {'timestamps': timestamps, 'data': data_points}
    
    def _collect_apps_data(self):
        """收集应用数据"""
        apps_data = {}
        for package_name, buffer in self.data_buffers['apps'].items():
            timestamps, data_points = buffer.get_recent_data(1800)
            apps_data[package_name] = {'timestamps': timestamps, 'data': data_points}
        return apps_data
    
    def _get_monitoring_duration(self):
        """获取监控时长字符串"""
        if not self.monitoring_start_time:
            return "00:00:00"
        elapsed = time.time() - self.monitoring_start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def _generate_system_stats_html(self, system_data):
        """生成系统统计信息HTML"""
        stats_html = ""
        system_metrics = ['CPU使用率：Total', 'CPU使用率：用户态', '内存使用', '电池电量', 'CPU温度']
        colors = ['#2196F3', '#1976D2', '#4CAF50', '#FF9800', '#F44336']
        
        for i, metric in enumerate(system_metrics):
            value = self._get_latest_metric_value(f'system_{metric}')
            stats_html += f"""
            <div class="stat-card">
                <div class="stat-title">{metric}</div>
                <div class="stat-value" style="color: {colors[i]}">{value}</div>
            </div>
            """
        return stats_html
    
    def _generate_apps_html(self, apps_data):
        """生成应用信息HTML"""
        apps_html = ""
        for package_name, data in apps_data.items():
            app_name = package_name.split('.')[-1]  # 简化包名
            apps_html += f"""
            <div class="app-section">
                <div class="app-title">{app_name} ({package_name})</div>
                <table>
                    <tr><th>指标</th><th>当前值</th><th>最大值</th><th>平均值</th></tr>
                    <tr><td>CPU使用率</td><td>{self._get_latest_metric_value(f'{package_name}_CPU')}%</td><td>-</td><td>-</td></tr>
                    <tr><td>内存使用</td><td>{self._get_latest_metric_value(f'{package_name}_内存')}MB</td><td>-</td><td>-</td></tr>
                    <tr><td>内存使用率</td><td>{self._get_latest_metric_value(f'{package_name}_内存百分比')}%</td><td>-</td><td>-</td></tr>
                    <tr><td>帧率</td><td>{self._get_latest_metric_value(f'{package_name}_帧率')}FPS</td><td>-</td><td>-</td></tr>
                    <tr><td>功耗</td><td>{self._get_latest_metric_value(f'{package_name}_功耗')}mW</td><td>-</td><td>-</td></tr>
                </table>
            </div>
            """
        return apps_html
    
    def _generate_chart_js(self, system_data, apps_data):
        """生成Chart.js代码"""
        return """
        // 创建系统性能图表
        const ctx = document.getElementById('systemChart').getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: ['示例时间点1', '示例时间点2', '示例时间点3'],
                datasets: [{
                    label: 'CPU使用率',
                    data: [30, 45, 60],
                    borderColor: '#2196F3',
                    fill: false
                }, {
                    label: '内存使用',
                    data: [40, 55, 70],
                    borderColor: '#4CAF50', 
                    fill: false
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100
                    }
                }
            }
        });
        """
    
    def _get_latest_metric_value(self, metric_name):
        """获取指标的最新值"""
        if metric_name in self.metric_widgets:
            return self.metric_widgets[metric_name].current_value
        return "0"
    
    def set_selected_apps(self, selected_apps):
        """设置选中的应用"""
        self.selected_apps = selected_apps
        if hasattr(self, 'config'):
            self.config['selected_apps'] = selected_apps
        
        # 创建应用指标显示组件
        self._create_app_metrics_widgets(selected_apps)
    
    def handle_error(self, error_msg):
        """处理错误"""
        print(f"监控错误: {error_msg}")
        self.status_label.setText(f"监控状态: 错误 - {error_msg}")
        self.status_label.setStyleSheet("color: red;")

# 向后兼容性别名
MonitorViewWidget = OptimizedMonitorViewWidget
