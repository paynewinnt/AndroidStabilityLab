# -*- coding: utf-8 -*-
"""
Modern Main Window with Enhanced UI
Features:
- Modern flat design with gradient backgrounds
- Animated transitions
- Dark/Light theme support
- Responsive layout
- Enhanced visual effects
"""

import sys
import os
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QTabWidget, QLabel, QStatusBar, QMenuBar, QAction,
                           QMessageBox, QProgressBar, QSplitter, QPushButton,
                           QGraphicsDropShadowEffect, QFrame, QToolBar,
                           QListWidget, QTextEdit, QSlider,
                           QSpinBox, QGroupBox, QRadioButton, QButtonGroup,
                           QComboBox, QCheckBox, QSizePolicy)
from PyQt5.QtCore import (Qt, QTimer, pyqtSignal, QPropertyAnimation, 
                         QEasingCurve, QRect, QPoint, QParallelAnimationGroup,
                         QSequentialAnimationGroup, pyqtProperty)
from PyQt5.QtGui import (QFont, QIcon, QPalette, QColor, QLinearGradient,
                        QPainter, QBrush, QPen, QPixmap, QFontDatabase)

# Import existing components
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from .app_selector import AppSelectorWidget
from .monitor_view import MonitorViewWidget
from .device_connection import DeviceConnectionDialog
from .apk_manager import APKManagerDialog

class AnimatedButton(QPushButton):
    """Custom animated button with hover effects"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setMouseTracking(True)
        
        # Default colors - initialize first
        self._normal_color = QColor(70, 130, 180)  # Steel Blue
        self._hover_color = QColor(100, 149, 237)  # Cornflower Blue
        self._pressed_color = QColor(65, 105, 225)  # Royal Blue
        self._current_color = self._normal_color
        
        # Initialize animation after color properties
        self._animation = QPropertyAnimation(self, b"color")
        self._animation.setDuration(200)
        self._animation.setEasingCurve(QEasingCurve.InOutQuad)
        
        # Apply shadow effect
        self.shadow = QGraphicsDropShadowEffect()
        self.shadow.setBlurRadius(15)
        self.shadow.setXOffset(0)
        self.shadow.setYOffset(3)
        self.shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(self.shadow)
        
        self.update_style()
        
    def get_color(self):
        if hasattr(self, '_current_color'):
            return self._current_color
        return QColor(70, 130, 180)  # Default fallback
    
    def set_color(self, color):
        self._current_color = color
        self.update_style()
        
    color = pyqtProperty(QColor, get_color, set_color)
    
    def update_style(self):
        """Update button style based on current color"""
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._current_color.name()};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
                min-width: 120px;
            }}
            QPushButton:pressed {{
                background-color: {self._pressed_color.name()};
            }}
        """)
        
    def enterEvent(self, event):
        self._animation.setStartValue(self._current_color)
        self._animation.setEndValue(self._hover_color)
        self._animation.start()
        # Enhance shadow on hover
        self.shadow.setBlurRadius(20)
        self.shadow.setYOffset(5)
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self._animation.setStartValue(self._current_color)
        self._animation.setEndValue(self._normal_color)
        self._animation.start()
        # Reset shadow
        self.shadow.setBlurRadius(15)
        self.shadow.setYOffset(3)
        super().leaveEvent(event)

class ModernTabWidget(QTabWidget):
    """Custom tab widget with modern styling"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabPosition(QTabWidget.North)
        self.setMovable(True)
        self.setDocumentMode(True)
        
        # Apply modern styling
        self.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #ffffff;
                border-radius: 10px;
            }
            
            QTabWidget::tab-bar {
                alignment: left;
            }
            
            QTabBar::tab {
                background-color: #f0f0f0;
                color: #666666;
                padding: 12px 20px;
                margin: 2px;
                border-radius: 8px 8px 0 0;
                min-width: 120px;
                font-weight: 500;
            }
            
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #4682B4;
                font-weight: bold;
            }
            
            QTabBar::tab:hover:!selected {
                background-color: #e0e0e0;
            }
        """)


class ModernStatusBar(QStatusBar):
    """Enhanced status bar with animations"""
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Create status widgets
        self.connection_indicator = self.create_indicator("Connection")
        self.monitoring_indicator = self.create_indicator("Monitoring")
        self.data_rate_label = QLabel("0 KB/s")
        self.cpu_usage_bar = self.create_mini_progress("CPU")
        self.memory_usage_bar = self.create_mini_progress("MEM")
        
        # Add widgets
        self.addWidget(self.connection_indicator)
        self.addWidget(self.monitoring_indicator)
        self.addPermanentWidget(self.data_rate_label)
        self.addPermanentWidget(self.cpu_usage_bar)
        self.addPermanentWidget(self.memory_usage_bar)
        
        # Apply styling
        self.setStyleSheet("""
            QStatusBar {
                background: linear-gradient(to right, #f8f9fa, #e9ecef);
                border-top: 1px solid #dee2e6;
                padding: 5px;
            }
            QLabel {
                color: #495057;
                font-size: 12px;
                margin: 0 10px;
            }
        """)
        
    def create_indicator(self, name):
        """Create status indicator with icon"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 0, 5, 0)
        
        # Status light (colored circle)
        status_light = QLabel("●")
        status_light.setStyleSheet("color: #dc3545; font-size: 16px;")
        layout.addWidget(status_light)
        
        # Status text
        status_text = QLabel(f"{name}: Disconnected")
        layout.addWidget(status_text)
        
        widget.status_light = status_light
        widget.status_text = status_text
        
        return widget
        
    def create_mini_progress(self, label):
        """Create mini progress bar for resource monitoring"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 0, 5, 0)
        
        label_widget = QLabel(f"{label}:")
        layout.addWidget(label_widget)
        
        progress = QProgressBar()
        progress.setMaximumWidth(100)
        progress.setMaximumHeight(15)
        progress.setTextVisible(True)
        progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #dee2e6;
                border-radius: 7px;
                background-color: #f8f9fa;
                text-align: center;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background: linear-gradient(to right, #4682B4, #6495ED);
                border-radius: 6px;
            }
        """)
        layout.addWidget(progress)
        
        widget.progress = progress
        return widget
        
    def set_connection_status(self, connected):
        """Update connection status"""
        if connected:
            self.connection_indicator.status_light.setStyleSheet("color: #28a745; font-size: 16px;")
            self.connection_indicator.status_text.setText("连接: 活动")
        else:
            self.connection_indicator.status_light.setStyleSheet("color: #dc3545; font-size: 16px;")
            self.connection_indicator.status_text.setText("连接: 断开")
            
    def set_monitoring_status(self, active):
        """Update monitoring status"""
        if active:
            self.monitoring_indicator.status_light.setStyleSheet("color: #28a745; font-size: 16px;")
            self.monitoring_indicator.status_text.setText("监控: 运行中")
        else:
            self.monitoring_indicator.status_light.setStyleSheet("color: #ffc107; font-size: 16px;")
            self.monitoring_indicator.status_text.setText("监控: 已停止")

class ModernMainWindow(QMainWindow):
    """Modern enhanced main window with improved UI/UX"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AndroidMetrics")
        self.setGeometry(100, 100, 1400, 900)
        
        # 设置窗口图标
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icons", "androidmetrics_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # Enable window animations
        self.setWindowFlags(Qt.Window | Qt.WindowSystemMenuHint | 
                           Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | 
                           Qt.WindowCloseButtonHint)
        
        # Initialize device connection state
        self.connected_devices = []
        self.device_connection_dialog = None
        self.apk_manager_dialog = None
        
        # Initialize components
        self.init_ui()
        self.apply_modern_theme()
        self.setup_animations()
        self.check_initial_device_status()
        
    def init_ui(self):
        """Initialize modern UI components"""
        # Create central widget with gradient background
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create custom toolbar
        self.create_modern_toolbar()
        
        # Create tab widget
        self.tab_widget = ModernTabWidget()
        
        # Add tabs with icons - 使用现代化组件
        try:
            from .modern_app_selector import ModernAppSelectorWidget
            self.app_selector = ModernAppSelectorWidget()
        except ImportError:
            from .app_selector import AppSelectorWidget
            self.app_selector = AppSelectorWidget()
            
        self.monitor_view = MonitorViewWidget()
        
        # Add a welcome/dashboard tab
        dashboard = self.create_dashboard()
        self.tab_widget.addTab(dashboard, "🏠 仪表板")
        
        # Create tools tab with device connection and APK management
        tools_tab = self.create_tools_tab()
        self.tab_widget.addTab(tools_tab, "🔧 工具")
        
        self.tab_widget.addTab(self.app_selector, "📱 应用选择")
        self.tab_widget.addTab(self.monitor_view, "📊 性能监控")
        
        self.tab_widget.setCurrentIndex(0)
        
        # Create container with padding
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(20, 20, 20, 20)
        container_layout.addWidget(self.tab_widget)
        
        main_layout.addWidget(container)
        
        # Create modern status bar
        self.status_bar = ModernStatusBar()
        self.setStatusBar(self.status_bar)
        
        
        # Create menu bar
        self.create_modern_menu()
        
    def create_modern_toolbar(self):
        """Create simplified modern toolbar"""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #ffffff;
                border-bottom: 1px solid #e9ecef;
                padding: 12px 20px;
                spacing: 10px;
            }
        """)
        
        
        # Add spacer to center the title
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        toolbar.addWidget(spacer)
        
        # Add status indicator
        self.status_label = QLabel("📱 准备就绪")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #6c757d;
                font-size: 13px;
                font-weight: 500;
                padding: 6px 12px;
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 20px;
                margin: 0 10px;
            }
        """)
        toolbar.addWidget(self.status_label)
        
        self.addToolBar(toolbar)
        
    def create_dashboard(self):
        """Create dashboard with overview information"""
        dashboard = QWidget()
        layout = QVBoxLayout(dashboard)
        
        # Welcome section
        welcome_frame = QFrame()
        welcome_frame.setStyleSheet("""
            QFrame {
                background: linear-gradient(to right, #667eea, #764ba2);
                border-radius: 15px;
                padding: 20px;
            }
        """)
        welcome_layout = QVBoxLayout(welcome_frame)
        
        
        layout.addWidget(welcome_frame)
        
        # Stats cards
        stats_layout = QHBoxLayout()
        
        # Create stat cards
        cards_data = [
            ("📱", "已连接设备", "0", "#4CAF50"),
            ("📊", "活动监控", "0", "#2196F3"),
            ("💾", "数据点", "0", "#FF9800"),
            ("⚡", "平均CPU使用率", "0%", "#9C27B0")
        ]
        
        for icon, title, value, color in cards_data:
            card = self.create_stat_card(icon, title, value, color)
            stats_layout.addWidget(card)
            
        layout.addLayout(stats_layout)
        
        # Recent activity
        activity_frame = QFrame()
        activity_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 10px;
                border: 1px solid #e0e0e0;
            }
        """)
        activity_layout = QVBoxLayout(activity_frame)
        
        activity_title = QLabel("📋 最近活动")
        activity_title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #333;
                padding: 10px;
            }
        """)
        activity_layout.addWidget(activity_title)
        
        activity_list = QListWidget()
        activity_list.addItems([
            "✅ 系统启动成功",
            "🔍 等待设备连接...",
            "🚀 准备开始监控"
        ])
        activity_list.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: transparent;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
        """)
        activity_layout.addWidget(activity_list)
        
        layout.addWidget(activity_frame)
        layout.addStretch()
        
        return dashboard
        
    def create_stat_card(self, icon, title, value, color):
        """Create a statistics card widget"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border-radius: 10px;
                border: 1px solid #e0e0e0;
                padding: 15px;
            }}
            QFrame:hover {{
                border: 2px solid {color};
                background-color: #fafafa;
            }}
        """)
        
        # Add shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 50))
        card.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(card)
        
        # Icon
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"""
            QLabel {{
                font-size: 32px;
                color: {color};
            }}
        """)
        layout.addWidget(icon_label, alignment=Qt.AlignCenter)
        
        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #666;
                font-weight: 500;
            }
        """)
        layout.addWidget(title_label, alignment=Qt.AlignCenter)
        
        # Value
        value_label = QLabel(value)
        value_label.setStyleSheet(f"""
            QLabel {{
                font-size: 24px;
                font-weight: bold;
                color: {color};
            }}
        """)
        layout.addWidget(value_label, alignment=Qt.AlignCenter)
        
        return card
    
    def create_tools_tab(self):
        """创建工具标签页"""
        tools_widget = QWidget()
        tools_layout = QVBoxLayout(tools_widget)
        tools_layout.setSpacing(20)
        tools_layout.setContentsMargins(30, 30, 30, 30)
        
        # 标题
        title_label = QLabel("🔧 工具集合")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #495057;
                margin-bottom: 20px;
            }
        """)
        tools_layout.addWidget(title_label)
        
        # 工具按钮容器
        buttons_frame = QFrame()
        buttons_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e9ecef;
                padding: 20px;
            }
        """)
        buttons_layout = QVBoxLayout(buttons_frame)
        buttons_layout.setSpacing(15)
        
        # 设备连接按钮
        device_btn = QPushButton("📱 设备连接")
        device_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: black;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 15px 20px;
                font-size: 16px;
                font-weight: bold;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #f8f9fa;
                border-color: #adb5bd;
            }
            QPushButton:pressed {
                background-color: #e9ecef;
            }
        """)
        device_btn.clicked.connect(self.open_device_connection)
        buttons_layout.addWidget(device_btn)
        
        # APK管理按钮
        apk_btn = QPushButton("📦 APK管理")
        apk_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: black;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 15px 20px;
                font-size: 16px;
                font-weight: bold;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #f8f9fa;
                border-color: #adb5bd;
            }
            QPushButton:pressed {
                background-color: #e9ecef;
            }
        """)
        apk_btn.clicked.connect(self.open_apk_manager)
        buttons_layout.addWidget(apk_btn)
        
        tools_layout.addWidget(buttons_frame)
        
        # 添加弹性空间
        tools_layout.addStretch()
        
        return tools_widget
        
    def create_modern_menu(self):
        """Create modern menu bar"""
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #f8f9fa;
                border-bottom: 1px solid #dee2e6;
                padding: 5px;
            }
            QMenuBar::item {
                padding: 8px 15px;
                margin: 0 2px;
                border-radius: 5px;
            }
            QMenuBar::item:selected {
                background-color: #e9ecef;
            }
            QMenu {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 5px;
                padding: 5px;
            }
            QMenu::item {
                padding: 8px 30px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #4682B4;
                color: white;
            }
        """)
        
        # Tools menu
        tools_menu = menubar.addMenu("🔧 工具")
        tools_menu.addAction("📱 设备连接", self.open_device_connection)
        tools_menu.addAction("📦 APK管理", self.open_apk_manager)
        tools_menu.addSeparator()
        tools_menu.addAction("📈 性能分析器", self.performance_analyzer)
        tools_menu.addAction("🔍 日志查看器", self.log_viewer)
        
        # Settings menu
        settings_menu = menubar.addMenu("⚙ 设置")
        settings_menu.addAction("🎨 主题设置", self.theme_settings)
        settings_menu.addAction("📐 布局选项", self.layout_options)
        settings_menu.addAction("🔧 工具栏", self.toggle_toolbar)
        settings_menu.addSeparator()
        settings_menu.addAction("⚙ 首选项", self.preferences)
        
        # File menu
        file_menu = menubar.addMenu("📁 文件")
        file_menu.addAction("📂 打开会话", self.open_session)
        file_menu.addAction("💾 保存会话", self.save_session)
        file_menu.addSeparator()
        file_menu.addAction("📊 导出数据", self.export_data)
        file_menu.addSeparator()
        file_menu.addAction("❌ 退出", self.close)
        
        # View menu
        view_menu = menubar.addMenu("👁 视图")
        view_menu.addAction("🏠 仪表板", lambda: self.tab_widget.setCurrentIndex(0))
        view_menu.addAction("📱 应用选择", lambda: self.tab_widget.setCurrentIndex(1))
        view_menu.addAction("📊 性能监控", lambda: self.tab_widget.setCurrentIndex(2))
        view_menu.addSeparator()
        view_menu.addAction("🔄 刷新界面", self.refresh_interface)
        
        # Help menu
        help_menu = menubar.addMenu("帮助")
        help_menu.addAction("📖 使用文档", self.show_docs)
        help_menu.addAction("🎯 快速入门指南", self.quick_start)
        help_menu.addSeparator()
        help_menu.addAction("ℹ 关于", self.show_about)
        
    def apply_modern_theme(self):
        """Apply modern theme to the application"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            
            QWidget {
                font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                font-size: 13px;
            }
            
            QPushButton {
                background-color: #4682B4;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
                min-width: 100px;
            }
            
            QPushButton:hover {
                background-color: #5F9EA0;
            }
            
            QPushButton:pressed {
                background-color: #4169E1;
            }
            
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            
            QGroupBox {
                font-weight: bold;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px;
                color: #495057;
            }
            
            QComboBox {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 6px;
                background-color: white;
            }
            
            QComboBox:hover {
                border-color: #4682B4;
            }
            
            QComboBox::drop-down {
                border: none;
            }
            
            QSpinBox {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 6px;
                background-color: white;
            }
            
            QSpinBox:hover {
                border-color: #4682B4;
            }
            
            
        """)
        
    def setup_animations(self):
        """Setup animations for UI elements"""
        # Window fade-in animation
        self.setWindowOpacity(0)
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(500)
        self.fade_animation.setStartValue(0)
        self.fade_animation.setEndValue(1)
        self.fade_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.fade_animation.start()
        
    # Placeholder methods for menu actions
    def open_session(self): 
        QMessageBox.information(self, "打开会话", "📂 会话管理功能开发中...\n\n即将支持保存和恢复监控会话！")
        
    def save_session(self): 
        QMessageBox.information(self, "保存会话", "💾 会话保存功能开发中...\n\n即将支持保存当前监控状态！")
        
    def export_data(self): 
        QMessageBox.information(self, "导出数据", "📊 数据导出功能开发中...\n\n即将支持多种格式的数据导出！")
        
    def theme_settings(self): 
        QMessageBox.information(self, "主题设置", "🎨 主题设置功能开发中...\n\n即将支持深色/浅色主题切换！")
        
    def layout_options(self): 
        QMessageBox.information(self, "布局选项", "📐 布局设置功能开发中...\n\n即将支持自定义界面布局！")
        
    def toggle_toolbar(self): 
        # 获取所有工具栏
        toolbars = self.findChildren(QToolBar)
        if toolbars:
            toolbar = toolbars[0]
            if toolbar.isVisible():
                toolbar.hide()
                QMessageBox.information(self, "工具栏", "🔧 工具栏已隐藏")
            else:
                toolbar.show()
                QMessageBox.information(self, "工具栏", "🔧 工具栏已显示")
        else:
            QMessageBox.information(self, "工具栏", "⚠️ 未找到工具栏")
            
    def performance_analyzer(self): 
        QMessageBox.information(self, "性能分析器", "📈 性能分析器功能开发中...\n\n即将提供深度性能分析工具！")
        
    def log_viewer(self): 
        QMessageBox.information(self, "日志查看器", "🔍 日志查看器功能开发中...\n\n即将支持实时日志查看！")
        
    def preferences(self): 
        QMessageBox.information(self, "首选项", "⚙️ 首选项设置功能开发中...\n\n即将提供详细的应用配置选项！")
        
    def show_docs(self): 
        QMessageBox.information(self, "使用文档", "📖 使用文档功能开发中...\n\n即将提供完整的用户手册！")
        
    def quick_start(self): 
        QMessageBox.information(self, "快速入门", "🎯 快速入门指南开发中...\n\n即将提供新手引导教程！")
        
    def refresh_interface(self):
        """刷新界面"""
        QMessageBox.information(self, "刷新界面", "🔄 界面已刷新！")
    
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(self, "关于AndroidMetrics",
            """<h2>AndroidMetrics</h2>
            <p><b>版本 2.0</b></p>
            <p>Android设备性能监控解决方案</p>
            <p>主要功能:</p>
            <ul>
                <li>实时性能监控</li>
                <li>现代化直观的用户界面</li>
                <li>高级数据可视化</li>
                <li>全面的数据导出功能</li>
            </ul>
            <p>© 2024 AndroidMetrics 开发团队</p>
            """)
    
    def open_device_connection(self):
        """打开设备连接对话框"""
        if self.device_connection_dialog is None:
            self.device_connection_dialog = DeviceConnectionDialog(self)
            self.device_connection_dialog.device_connected.connect(self.on_device_connected)
        
        self.device_connection_dialog.show()
        self.device_connection_dialog.raise_()
        self.device_connection_dialog.activateWindow()
    
    def open_apk_manager(self):
        """打开APK管理器对话框"""
        if self.apk_manager_dialog is None:
            self.apk_manager_dialog = APKManagerDialog(self)
        
        self.apk_manager_dialog.show()
        self.apk_manager_dialog.raise_()
        self.apk_manager_dialog.activateWindow()
    
    def on_device_connected(self, device_info):
        """设备连接成功处理"""
        if device_info not in self.connected_devices:
            self.connected_devices.append(device_info)
        
        # 更新状态显示
        self.update_device_status()
        
        # 更新状态栏
        if hasattr(self, 'status_bar'):
            self.status_bar.set_connection_status(True)
        
        # 显示成功消息
        QMessageBox.information(self, "设备连接成功", 
                              f"✅ 设备连接成功！\n设备: {device_info}\n\n现在可以开始性能监控了。")
    
    def update_device_status(self):
        """更新设备连接状态显示"""
        device_count = len(self.connected_devices)
        
        if device_count == 0:
            status_text = "📱 无设备连接"
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #dc3545;
                    font-size: 13px;
                    font-weight: 500;
                    padding: 6px 12px;
                    background-color: #fff5f5;
                    border: 1px solid #f5c2c7;
                    border-radius: 20px;
                    margin: 0 10px;
                }
            """)
        elif device_count == 1:
            status_text = "📱 1台设备已连接"
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #28a745;
                    font-size: 13px;
                    font-weight: 500;
                    padding: 6px 12px;
                    background-color: #f5fdf7;
                    border: 1px solid #c3e6cb;
                    border-radius: 20px;
                    margin: 0 10px;
                }
            """)
        else:
            status_text = f"📱 {device_count}台设备已连接"
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #28a745;
                    font-size: 13px;
                    font-weight: 500;
                    padding: 6px 12px;
                    background-color: #f5fdf7;
                    border: 1px solid #c3e6cb;
                    border-radius: 20px;
                    margin: 0 10px;
                }
            """)
        
        self.status_label.setText(status_text)
        
        # 更新仪表盘统计卡片
        self.update_dashboard_stats()
    
    def update_dashboard_stats(self):
        """更新仪表盘统计信息"""
        # 这里可以根据实际需要更新仪表盘中的统计卡片
        # 例如更新"已连接设备"卡片的数值
        pass
    
    def check_initial_device_status(self):
        """检查初始设备连接状态"""
        try:
            import subprocess
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # 跳过标题行
                connected_devices = []
                
                for line in lines:
                    if line.strip() and 'device' in line:
                        device_id = line.split()[0]
                        connected_devices.append(device_id)
                
                self.connected_devices = connected_devices
                self.update_device_status()
                
                # 更新状态栏
                if hasattr(self, 'status_bar'):
                    self.status_bar.set_connection_status(len(connected_devices) > 0)
        except:
            # ADB不可用或其他错误，保持默认状态
            pass

