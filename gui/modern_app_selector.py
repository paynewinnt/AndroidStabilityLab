# -*- coding: utf-8 -*-
"""
Modern App Selector Widget with Enhanced UI
现代化应用选择器组件，优化的PyQt5界面
"""

import sys
import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                           QListWidgetItem, QPushButton, QLabel, QLineEdit,
                           QGroupBox, QCheckBox, QSpinBox, QComboBox,
                           QMessageBox, QProgressDialog, QFrame, QScrollArea,
                           QGraphicsDropShadowEffect, QSizePolicy, QSpacerItem)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, pyqtSlot, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont, QColor, QIcon, QPainter, QBrush, QPen

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class ModernButton(QPushButton):
    """现代化按钮组件"""
    def __init__(self, text="", button_type="default", parent=None):
        super().__init__(text, parent)
        self.button_type = button_type
        self.setup_style()
        self.setup_shadow()
        
    def setup_style(self):
        """设置按钮样式"""
        if self.button_type == "primary":
            self.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #4CAF50, stop:1 #45a049);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 12px 24px;
                    font-size: 14px;
                    font-weight: bold;
                    min-height: 20px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #5cbf60, stop:1 #4CAF50);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #45a049, stop:1 #3d8b40);
                }
                QPushButton:disabled {
                    background: #cccccc;
                    color: #666666;
                }
            """)
        elif self.button_type == "danger":
            self.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #f44336, stop:1 #da190b);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 12px 24px;
                    font-size: 14px;
                    font-weight: bold;
                    min-height: 20px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #f66356, stop:1 #f44336);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #da190b, stop:1 #c1160a);
                }
                QPushButton:disabled {
                    background: #cccccc;
                    color: #666666;
                }
            """)
        else:  # default
            self.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #f8f9fa, stop:1 #e9ecef);
                    color: #495057;
                    border: 1px solid #ced4da;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-size: 13px;
                    font-weight: 500;
                    min-height: 16px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #e9ecef, stop:1 #dee2e6);
                    border-color: #4682B4;
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #dee2e6, stop:1 #ced4da);
                }
            """)
            
    def setup_shadow(self):
        """设置阴影效果"""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)

class ModernGroupBox(QGroupBox):
    """现代化分组框"""
    def __init__(self, title="", parent=None):
        super().__init__(title, parent)
        self.setup_style()
        
    def setup_style(self):
        """设置样式"""
        self.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 2px solid #e9ecef;
                border-radius: 10px;
                margin: 15px 5px 5px 5px;
                padding-top: 20px;
                background-color: white;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
                color: #4682B4;
                background-color: white;
            }
        """)
        
        # 添加阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 20))
        self.setGraphicsEffect(shadow)

class ModernListWidget(QListWidget):
    """现代化列表组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_style()
        
    def setup_style(self):
        """设置样式"""
        self.setStyleSheet("""
            QListWidget {
                border: 1px solid #dee2e6;
                border-radius: 8px;
                background-color: white;
                selection-background-color: #4682B4;
                selection-color: white;
                outline: none;
                font-size: 13px;
            }
            
            QListWidget::item {
                padding: 12px 15px;
                border-bottom: 1px solid #f8f9fa;
                background-color: white;
            }
            
            QListWidget::item:hover {
                background-color: #f8f9fa;
            }
            
            QListWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4682B4, stop:1 #5F9EA0);
                color: white;
                border-bottom-color: #4682B4;
            }
            
            QListWidget::item:selected:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5F9EA0, stop:1 #4682B4);
            }
        """)

class ModernAppSelectorWidget(QWidget):
    """现代化应用选择器组件"""
    # 信号定义
    apps_selected = pyqtSignal(list)  # 应用选择信号
    monitoring_started = pyqtSignal(dict)  # 监控开始信号
    monitoring_stopped = pyqtSignal()  # 监控停止信号
    
    def __init__(self):
        super().__init__()
        self.apps_list = []
        self.selected_apps = []
        self.monitoring_active = False
        
        self.init_ui()
        
    def init_ui(self):
        """初始化现代化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 设置背景色
        self.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
            }
        """)
        
        # 不再创建标题区域
        # self.create_modern_header(layout)
        
        # 创建主内容区域
        main_layout = QHBoxLayout()
        main_layout.setSpacing(20)
        layout.addLayout(main_layout)
        
        # 应用列表区域 (左侧)
        self.create_app_list_section(main_layout)
        
        # 监控配置区域 (右侧)
        self.create_config_section(main_layout)
        
        # 创建操作按钮区域
        self.create_action_buttons(layout)
        
    def create_modern_header(self, layout):
        """创建现代化标题区域"""
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 15px;
                padding: 20px;
            }
        """)
        
        # 添加阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(3)
        shadow.setColor(QColor(0, 0, 0, 30))
        header_frame.setGraphicsEffect(shadow)
        
        header_layout = QVBoxLayout(header_frame)
        
        # 主标题
        title_label = QLabel("📱 Android应用性能监控")
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 24px;
                font-weight: bold;
                margin: 0;
                padding: 0;
            }
        """)
        title_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(title_label)
        
        # 副标题
        subtitle_label = QLabel("选择要监控的Android应用，配置监控参数，开始专业性能分析")
        subtitle_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.9);
                font-size: 14px;
                margin: 8px 0 0 0;
                padding: 0;
            }
        """)
        subtitle_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(subtitle_label)
        
        layout.addWidget(header_frame)
        
    def create_app_list_section(self, layout):
        """创建现代化应用列表区域"""
        app_group = ModernGroupBox("🔍 应用列表")
        app_layout = QVBoxLayout(app_group)
        app_layout.setSpacing(15)
        
        # 搜索和过滤区域
        filter_container = QFrame()
        filter_container.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        filter_layout = QVBoxLayout(filter_container)
        
        # 搜索框
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 搜索:")
        search_label.setStyleSheet("font-weight: bold; color: #495057;")
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入应用名称或包名进行搜索...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #ced4da;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #4682B4;
            }
        """)
        self.search_input.textChanged.connect(self.filter_apps)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        filter_layout.addLayout(search_layout)
        
        # 应用类型过滤
        type_layout = QHBoxLayout()
        type_label = QLabel("📂 类型:")
        type_label.setStyleSheet("font-weight: bold; color: #495057;")
        
        self.app_type_combo = QComboBox()
        self.app_type_combo.addItems(["所有应用", "仅第三方应用", "仅系统应用"])
        self.app_type_combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #ced4da;
                border-radius: 6px;
                padding: 8px 12px;
                background-color: white;
                font-size: 13px;
                min-width: 150px;
            }
            QComboBox:hover {
                border-color: #4682B4;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                width: 12px;
                height: 12px;
            }
        """)
        self.app_type_combo.currentTextChanged.connect(self.filter_apps)
        
        type_layout.addWidget(type_label)
        type_layout.addWidget(self.app_type_combo)
        type_layout.addStretch()
        filter_layout.addLayout(type_layout)
        
        app_layout.addWidget(filter_container)
        
        # 应用列表
        self.app_list = ModernListWidget()
        self.app_list.setSelectionMode(QListWidget.MultiSelection)
        self.app_list.itemSelectionChanged.connect(self.on_selection_changed)
        app_layout.addWidget(self.app_list)
        
        # 选择状态标签
        self.selection_label = QLabel("已选择: 0 / 6")
        self.selection_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #4682B4;
                background-color: #e3f2fd;
                border: 1px solid #bbdefb;
                border-radius: 15px;
                padding: 8px 16px;
            }
        """)
        self.selection_label.setAlignment(Qt.AlignCenter)
        app_layout.addWidget(self.selection_label)
        
        layout.addWidget(app_group, 2)  # 占2/3宽度
        
    def create_config_section(self, layout):
        """创建现代化监控配置区域"""
        config_group = ModernGroupBox("⚙ 监控配置")
        config_layout = QVBoxLayout(config_group)
        config_layout.setSpacing(15)
        
        # 采样配置区域
        sampling_group = ModernGroupBox("⏱ 采样设置")
        sampling_layout = QVBoxLayout(sampling_group)
        sampling_layout.setSpacing(10)
        
        # 采样间隔
        interval_layout = QHBoxLayout()
        interval_label = QLabel("采样间隔:")
        interval_label.setStyleSheet("font-weight: bold; color: #495057;")
        
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(3)
        self.interval_spin.setSuffix(" 秒")
        self.interval_spin.setStyleSheet("""
            QSpinBox {
                border: 2px solid #ced4da;
                border-radius: 6px;
                padding: 6px;
                background-color: white;
                font-size: 13px;
                min-width: 80px;
            }
            QSpinBox:hover {
                border-color: #4682B4;
            }
        """)
        
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(self.interval_spin)
        interval_layout.addStretch()
        sampling_layout.addLayout(interval_layout)
        
        # 监控时长
        duration_layout = QHBoxLayout()
        duration_label = QLabel("监控时长:")
        duration_label.setStyleSheet("font-weight: bold; color: #495057;")
        
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 1440)
        self.duration_spin.setValue(30)
        self.duration_spin.setSuffix(" 分钟")
        self.duration_spin.setStyleSheet("""
            QSpinBox {
                border: 2px solid #ced4da;
                border-radius: 6px;
                padding: 6px;
                background-color: white;
                font-size: 13px;
                min-width: 80px;
            }
            QSpinBox:hover {
                border-color: #4682B4;
            }
        """)
        
        duration_layout.addWidget(duration_label)
        duration_layout.addWidget(self.duration_spin)
        duration_layout.addStretch()
        sampling_layout.addLayout(duration_layout)
        
        # 连续监控模式
        self.continuous_check = QCheckBox("🔄 连续监控模式（不限时间）")
        self.continuous_check.setStyleSheet("""
            QCheckBox {
                font-size: 13px;
                font-weight: 500;
                color: #495057;
                spacing: 8px;
            }
        """)
        sampling_layout.addWidget(self.continuous_check)
        
        config_layout.addWidget(sampling_group)
        
        # 监控指标区域
        metrics_group = ModernGroupBox("📊 监控指标")
        metrics_layout = QVBoxLayout(metrics_group)
        metrics_layout.setSpacing(8)
        
        # 创建指标复选框
        metrics_data = [
            ("🖥 CPU使用率", "cpu_check", True),
            ("💾 内存使用", "memory_check", True),
            ("🌐 网络流量", "network_check", True),
            ("🔋 功耗状态", "power_check", True),
            ("🎮 FPS帧率", "fps_check", True),
            ("⚡ 系统整体性能", "system_check", True)
        ]
        
        for text, attr_name, default_checked in metrics_data:
            checkbox = QCheckBox(text)
            checkbox.setChecked(default_checked)
            checkbox.setStyleSheet("""
                QCheckBox {
                    font-size: 13px;
                    color: #495057;
                    spacing: 8px;
                    padding: 4px;
                }
            """)
            setattr(self, attr_name, checkbox)
            metrics_layout.addWidget(checkbox)
            
        config_layout.addWidget(metrics_group)
        
        # 预设配置区域
        preset_group = ModernGroupBox("🎯 预设配置")
        preset_layout = QVBoxLayout(preset_group)
        
        preset_select_layout = QHBoxLayout()
        preset_label = QLabel("选择预设:")
        preset_label.setStyleSheet("font-weight: bold; color: #495057;")
        
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["标准监控", "性能测试", "长期监控", "自定义配置"])
        self.preset_combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #ced4da;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: white;
                font-size: 13px;
                min-width: 120px;
            }
            QComboBox:hover {
                border-color: #4682B4;
            }
        """)
        self.preset_combo.currentTextChanged.connect(self.on_preset_changed)
        
        preset_select_layout.addWidget(preset_label)
        preset_select_layout.addWidget(self.preset_combo)
        preset_select_layout.addStretch()
        preset_layout.addLayout(preset_select_layout)
        
        # 预设操作按钮
        preset_buttons_layout = QHBoxLayout()
        self.save_preset_btn = ModernButton("💾 保存配置", "default")
        self.save_preset_btn.clicked.connect(self.save_preset)
        
        self.load_preset_btn = ModernButton("📂 加载配置", "default")
        self.load_preset_btn.clicked.connect(self.load_preset)
        
        preset_buttons_layout.addWidget(self.save_preset_btn)
        preset_buttons_layout.addWidget(self.load_preset_btn)
        preset_layout.addLayout(preset_buttons_layout)
        
        config_layout.addWidget(preset_group)
        config_layout.addStretch()
        
        layout.addWidget(config_group, 1)  # 占1/3宽度
        
    def create_action_buttons(self, layout):
        """创建操作按钮区域"""
        button_container = QFrame()
        button_container.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        
        # 添加阴影
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 20))
        button_container.setGraphicsEffect(shadow)
        
        button_layout = QHBoxLayout(button_container)
        
        # 刷新按钮
        self.refresh_btn = ModernButton("🔄 刷新应用列表", "default")
        self.refresh_btn.clicked.connect(self.refresh_apps)
        button_layout.addWidget(self.refresh_btn)
        
        # 添加弹性空间
        button_layout.addStretch()
        
        # 状态指示器
        status_label = QLabel("📱 准备就绪")
        status_label.setStyleSheet("""
            QLabel {
                color: #28a745;
                font-size: 14px;
                font-weight: bold;
                padding: 8px;
            }
        """)
        button_layout.addWidget(status_label)
        
        button_layout.addStretch()
        
        # 主要操作按钮
        self.start_btn = ModernButton("▶ 开始监控", "primary")
        self.start_btn.clicked.connect(self.start_monitoring)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = ModernButton("⏹ 停止监控", "danger")
        self.stop_btn.clicked.connect(self.stop_monitoring)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)
        
        layout.addWidget(button_container)
        
    def set_apps(self, apps):
        """设置应用列表"""
        self.apps_list = apps
        self.update_app_list()
        
    def update_app_list(self):
        """更新应用列表显示"""
        self.app_list.clear()
        
        search_text = self.search_input.text().lower()
        app_type_filter = self.app_type_combo.currentText()
        
        for app in self.apps_list:
            app_name = app.get('app_name', app['package_name'])
            package_name = app['package_name']
            is_system = app.get('is_system', False)
            
            # 搜索过滤
            if search_text and search_text not in app_name.lower() and search_text not in package_name.lower():
                continue
                
            # 应用类型过滤
            if app_type_filter == "仅第三方应用" and is_system:
                continue
            elif app_type_filter == "仅系统应用" and not is_system:
                continue
                
            # 创建列表项
            if is_system:
                item_text = f"🏛 {app_name} [系统应用]\n📦 {package_name}"
            else:
                item_text = f"📱 {app_name}\n📦 {package_name}"
                
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, app)
            
            # 系统应用使用不同的样式
            if is_system:
                item.setForeground(QColor("#6c757d"))
            else:
                item.setForeground(QColor("#495057"))
            
            self.app_list.addItem(item)
            
    def filter_apps(self):
        """过滤应用列表"""
        self.update_app_list()
        
    def on_selection_changed(self):
        """选择变化处理"""
        selected_items = self.app_list.selectedItems()
        self.selected_apps = [item.data(Qt.UserRole) for item in selected_items]
        
        # 限制选择数量
        if len(self.selected_apps) > 6:
            # 取消最后一个选择
            selected_items[-1].setSelected(False)
            self.selected_apps = self.selected_apps[:6]
            QMessageBox.warning(self, "选择限制", 
                              "⚠ 为了确保监控性能，最多只能同时选择6个应用进行监控")
            
        # 更新选择状态
        self.selection_label.setText(f"已选择: {len(self.selected_apps)} / 6")
        
        # 更新开始按钮状态
        self.start_btn.setEnabled(len(self.selected_apps) > 0 and not self.monitoring_active)
        
        # 发送选择信号
        self.apps_selected.emit(self.selected_apps)
        
    def get_monitoring_config(self):
        """获取监控配置"""
        return {
            'selected_apps': self.selected_apps,
            'sample_interval': self.interval_spin.value(),
            'duration_minutes': self.duration_spin.value() if not self.continuous_check.isChecked() else 0,
            'continuous': self.continuous_check.isChecked(),
            'metrics': {
                'cpu': self.cpu_check.isChecked(),
                'memory': self.memory_check.isChecked(),
                'network': self.network_check.isChecked(),
                'power': self.power_check.isChecked(),
                'fps': self.fps_check.isChecked(),
                'system': self.system_check.isChecked()
            }
        }
        
    def start_monitoring(self):
        """开始监控"""
        if len(self.selected_apps) == 0:
            QMessageBox.warning(self, "⚠ 提示", "请先选择至少一个应用进行性能监控")
            return
            
        # 获取配置
        config = self.get_monitoring_config()
        
        # 创建确认对话框
        app_names = [app.get('app_name', app['package_name']) for app in self.selected_apps]
        message = "🚀 即将开始监控以下应用:\n\n"
        message += "\n".join(f"📱 {name}" for name in app_names)
        message += f"\n\n⚙ 监控配置:"
        message += f"\n• 采样间隔: {config['sample_interval']}秒"
        
        if config['continuous']:
            message += "\n• 监控模式: 连续监控"
        else:
            message += f"\n• 监控时长: {config['duration_minutes']}分钟"
            
        # 显示选中的监控指标
        enabled_metrics = [k for k, v in config['metrics'].items() if v]
        if enabled_metrics:
            message += f"\n• 监控指标: {', '.join(enabled_metrics).upper()}"
        
        reply = QMessageBox.question(
            self, '🚀 确认开始监控', message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            self.monitoring_active = True
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.monitoring_started.emit(config)
            
    def stop_monitoring(self):
        """停止监控"""
        reply = QMessageBox.question(
            self, '⏹ 确认停止监控', 
            '确定要停止当前的监控任务吗？\n\n⚠ 停止后当前的监控数据仍会保留。',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.monitoring_active = False
            self.start_btn.setEnabled(len(self.selected_apps) > 0)
            self.stop_btn.setEnabled(False)
            self.monitoring_stopped.emit()
            
    def refresh_apps(self):
        """刷新应用列表"""
        try:
            # 创建进度对话框
            progress = QProgressDialog("🔄 正在刷新应用列表，请稍候...", "取消", 0, 0, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setAutoClose(True)
            progress.setAutoReset(True)
            progress.show()
            
            # 获取父窗口的ADB收集器
            main_window = self.parent()
            while main_window and not hasattr(main_window, 'adb_collector'):
                main_window = main_window.parent()
                
            if main_window and hasattr(main_window, 'adb_collector') and main_window.adb_collector:
                # 重新获取应用列表
                apps = main_window.adb_collector.get_installed_apps()
                
                # 更新应用列表
                self.set_apps(apps)
                
                progress.close()
                QMessageBox.information(self, "✅ 刷新完成", 
                                      f"成功刷新应用列表！\n\n📱 共找到 {len(apps)} 个应用")
            else:
                progress.close()
                QMessageBox.warning(self, "❌ 刷新失败", 
                                  "无法连接到ADB服务\n\n请检查:\n• 设备连接状态\n• USB调试是否开启\n• ADB驱动是否正常")
                
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            QMessageBox.critical(self, "❌ 刷新错误", 
                               f"刷新应用列表时发生错误：\n\n{str(e)}")
        
    def on_preset_changed(self, preset_name):
        """预设配置变化"""
        if preset_name == "性能测试":
            self.interval_spin.setValue(1)
            self.duration_spin.setValue(15)
            self.continuous_check.setChecked(False)
        elif preset_name == "长期监控":
            self.interval_spin.setValue(10)
            self.duration_spin.setValue(360)
            self.continuous_check.setChecked(False)
        elif preset_name == "标准监控":
            self.interval_spin.setValue(3)
            self.duration_spin.setValue(30)
            self.continuous_check.setChecked(False)
            
    def save_preset(self):
        """保存预设配置"""
        QMessageBox.information(self, "💾 保存配置", 
                              "配置保存功能开发中...\n\n即将在后续版本中提供自定义预设保存功能！")
        
    def load_preset(self):
        """加载预设配置"""
        QMessageBox.information(self, "📂 加载配置", 
                              "配置加载功能开发中...\n\n即将在后续版本中提供自定义预设加载功能！")

# 为了保持兼容性，创建一个别名
AppSelectorWidget = ModernAppSelectorWidget