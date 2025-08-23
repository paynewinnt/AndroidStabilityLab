# -*- coding: utf-8 -*-
"""
APK安装管理模块
功能:
- 多选APK文件
- 多选目标设备
- 批量安装APK到设备
- 安装进度监控
- 错误处理和日志
"""

import os
import sys
import subprocess
import threading
import time
from typing import List, Dict, Tuple
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QListWidget, QListWidgetItem, 
                            QProgressBar, QTextEdit, QGroupBox, QCheckBox,
                            QFileDialog, QMessageBox, QTableWidget, 
                            QTableWidgetItem, QHeaderView, QSplitter,
                            QFrame, QGridLayout, QTabWidget, QWidget,
                            QScrollArea, QComboBox, QSpinBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QIcon, QFont, QColor, QPalette, QPixmap, QPainter

class APKInfo:
    """APK信息类"""
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)
        self.file_size = self.get_file_size()
        self.package_name = ""
        self.version_name = ""
        self.version_code = ""
        self.app_name = ""
        self.parse_apk_info()
    
    def get_file_size(self) -> str:
        """获取文件大小"""
        try:
            size = os.path.getsize(self.file_path)
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size / 1024:.1f} KB"
            else:
                return f"{size / (1024 * 1024):.1f} MB"
        except:
            return "未知"
    
    def parse_apk_info(self):
        """解析APK信息"""
        try:
            # 使用aapt解析APK信息
            result = subprocess.run(
                ["aapt", "dump", "badging", self.file_path],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    if line.startswith('package:'):
                        # 提取包名和版本信息
                        parts = line.split(' ')
                        for part in parts:
                            if part.startswith('name='):
                                self.package_name = part.split('=')[1].strip("'\"")
                            elif part.startswith('versionName='):
                                self.version_name = part.split('=')[1].strip("'\"")
                            elif part.startswith('versionCode='):
                                self.version_code = part.split('=')[1].strip("'\"")
                    elif line.startswith('application-label:'):
                        self.app_name = line.split(':')[1].strip().strip("'\"")
        except:
            # 如果aapt不可用，使用文件名作为应用名
            self.app_name = os.path.splitext(self.file_name)[0]

class InstallWorker(QThread):
    """APK安装工作线程"""
    progress_updated = pyqtSignal(str, str, int)  # device_id, apk_name, progress
    install_finished = pyqtSignal(str, str, bool, str)  # device_id, apk_name, success, message
    overall_progress = pyqtSignal(int)  # 总体进度
    log_message = pyqtSignal(str)
    
    def __init__(self, apk_files: List[str], devices: List[str]):
        super().__init__()
        self.apk_files = apk_files
        self.devices = devices
        self.total_tasks = len(apk_files) * len(devices)
        self.completed_tasks = 0
        self.running = True
    
    def run(self):
        """执行安装任务"""
        self.log_message.emit(f"🚀 开始批量安装，总任务数: {self.total_tasks}")
        
        for device_id in self.devices:
            if not self.running:
                break
                
            for apk_file in self.apk_files:
                if not self.running:
                    break
                
                apk_name = os.path.basename(apk_file)
                self.log_message.emit(f"📱 正在安装 {apk_name} 到设备 {device_id}")
                
                # 更新进度
                self.progress_updated.emit(device_id, apk_name, 0)
                
                try:
                    # 执行安装
                    success, message = self.install_apk(device_id, apk_file)
                    
                    # 更新完成状态
                    self.progress_updated.emit(device_id, apk_name, 100)
                    self.install_finished.emit(device_id, apk_name, success, message)
                    
                    if success:
                        self.log_message.emit(f"✅ {apk_name} 安装成功到 {device_id}")
                    else:
                        self.log_message.emit(f"❌ {apk_name} 安装失败到 {device_id}: {message}")
                        
                except Exception as e:
                    self.install_finished.emit(device_id, apk_name, False, str(e))
                    self.log_message.emit(f"❌ {apk_name} 安装出错: {str(e)}")
                
                # 更新总体进度
                self.completed_tasks += 1
                overall_percent = int((self.completed_tasks / self.total_tasks) * 100)
                self.overall_progress.emit(overall_percent)
                
                # 短暂延迟，避免过快操作
                time.sleep(0.5)
        
        self.log_message.emit("🎉 批量安装任务完成！")
    
    def install_apk(self, device_id: str, apk_file: str) -> Tuple[bool, str]:
        """安装单个APK到指定设备"""
        try:
            cmd = ["adb", "-s", device_id, "install", "-r", apk_file]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                if "Success" in result.stdout:
                    return True, "安装成功"
                else:
                    return False, result.stdout.strip()
            else:
                return False, result.stderr.strip()
                
        except subprocess.TimeoutExpired:
            return False, "安装超时"
        except Exception as e:
            return False, f"安装异常: {str(e)}"
    
    def stop(self):
        """停止安装"""
        self.running = False

class APKManagerDialog(QDialog):
    """APK安装管理对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📦 APK安装管理器")
        self.setModal(True)
        self.resize(900, 700)
        
        self.selected_apks: List[str] = []
        self.selected_devices: List[str] = []
        self.install_worker = None
        
        self.init_ui()
        self.apply_styles()
        self.refresh_devices()
        
        # 定时刷新设备列表
        self.device_timer = QTimer()
        self.device_timer.timeout.connect(self.refresh_devices)
        self.device_timer.start(5000)  # 每5秒刷新一次
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel("📦 APK批量安装管理器")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 22px;
                font-weight: bold;
                color: #2c3e50;
                padding: 15px;
                text-align: center;
                background: linear-gradient(to right, #3498db, #2980b9);
                color: white;
                border-radius: 8px;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(title_label)
        
        # 创建主体标签页
        self.tab_widget = QTabWidget()
        
        # APK选择标签页
        self.apk_tab = self.create_apk_tab()
        self.tab_widget.addTab(self.apk_tab, "📁 APK文件")
        
        # 设备选择标签页
        self.device_tab = self.create_device_tab()
        self.tab_widget.addTab(self.device_tab, "📱 目标设备")
        
        # 安装管理标签页
        self.install_tab = self.create_install_tab()
        self.tab_widget.addTab(self.install_tab, "⚙️ 安装管理")
        
        # 日志标签页
        self.log_tab = self.create_log_tab()
        self.tab_widget.addTab(self.log_tab, "📋 安装日志")
        
        layout.addWidget(self.tab_widget)
        
        # 底部操作按钮
        button_layout = QHBoxLayout()
        
        # 统计信息
        self.stats_label = QLabel("📊 APK: 0个, 设备: 0个")
        self.stats_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #7f8c8d;
                padding: 5px;
            }
        """)
        button_layout.addWidget(self.stats_label)
        
        button_layout.addStretch()
        
        # 操作按钮
        button_style = """
            QPushButton {
                background-color: white;
                color: #333333;
                border: 1px solid #dee2e6;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 500;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #f8f9fa;
                border-color: #4a90e2;
            }
            QPushButton:pressed {
                background-color: #e9ecef;
            }
            QPushButton:disabled {
                background-color: #f8f9fa;
                color: #6c757d;
                border-color: #dee2e6;
            }
        """
        
        self.start_install_btn = QPushButton("🚀 开始安装")
        self.start_install_btn.clicked.connect(self.start_installation)
        self.start_install_btn.setEnabled(False)
        self.start_install_btn.setStyleSheet(button_style)
        button_layout.addWidget(self.start_install_btn)
        
        self.stop_install_btn = QPushButton("⏹ 停止安装")
        self.stop_install_btn.clicked.connect(self.stop_installation)
        self.stop_install_btn.setEnabled(False)
        self.stop_install_btn.setStyleSheet(button_style)
        button_layout.addWidget(self.stop_install_btn)
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #333333;
                border: 1px solid #dee2e6;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 500;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #f8f9fa;
                border-color: #4a90e2;
            }
            QPushButton:pressed {
                background-color: #e9ecef;
            }
        """)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def create_apk_tab(self):
        """创建APK选择标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # APK文件选择组
        apk_group = QGroupBox("📁 APK文件选择")
        apk_layout = QVBoxLayout(apk_group)
        
        # 文件选择按钮
        file_buttons = QHBoxLayout()
        
        self.select_files_btn = QPushButton("📂 选择APK文件")
        self.select_files_btn.clicked.connect(self.select_apk_files)
        self.select_files_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #333333;
                border: 1px solid #dee2e6;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 500;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #f8f9fa;
                border-color: #4a90e2;
            }
            QPushButton:pressed {
                background-color: #e9ecef;
            }
        """)
        file_buttons.addWidget(self.select_files_btn)
        
        self.select_folder_btn = QPushButton("📁 选择文件夹")
        self.select_folder_btn.clicked.connect(self.select_apk_folder)
        self.select_folder_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #333333;
                border: 1px solid #dee2e6;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 500;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #f8f9fa;
                border-color: #4a90e2;
            }
            QPushButton:pressed {
                background-color: #e9ecef;
            }
        """)
        file_buttons.addWidget(self.select_folder_btn)
        
        self.clear_files_btn = QPushButton("🗑 清空列表")
        self.clear_files_btn.clicked.connect(self.clear_apk_list)
        self.clear_files_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #333333;
                border: 1px solid #dee2e6;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 500;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #f8f9fa;
                border-color: #4a90e2;
            }
            QPushButton:pressed {
                background-color: #e9ecef;
            }
        """)
        file_buttons.addWidget(self.clear_files_btn)
        
        file_buttons.addStretch()
        apk_layout.addLayout(file_buttons)
        
        # APK文件列表
        self.apk_table = QTableWidget()
        self.apk_table.setColumnCount(6)
        self.apk_table.setHorizontalHeaderLabels([
            "选择", "文件名", "应用名", "包名", "版本", "大小"
        ])
        
        # 设置列宽
        header = self.apk_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        
        self.apk_table.setColumnWidth(0, 60)
        self.apk_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.apk_table.setAlternatingRowColors(True)
        
        apk_layout.addWidget(self.apk_table)
        
        layout.addWidget(apk_group)
        
        return widget
    
    def create_device_tab(self):
        """创建设备选择标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 设备选择组
        device_group = QGroupBox("📱 目标设备选择")
        device_layout = QVBoxLayout(device_group)
        
        # 设备操作按钮
        device_buttons = QHBoxLayout()
        
        # 定义统一按钮样式
        button_style = """
            QPushButton {
                background-color: white;
                color: #333333;
                border: 1px solid #dee2e6;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 500;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #f8f9fa;
                border-color: #4a90e2;
            }
            QPushButton:pressed {
                background-color: #e9ecef;
            }
        """
        
        self.refresh_devices_btn = QPushButton("🔄 刷新设备")
        self.refresh_devices_btn.clicked.connect(self.refresh_devices)
        self.refresh_devices_btn.setStyleSheet(button_style)
        device_buttons.addWidget(self.refresh_devices_btn)
        
        self.select_all_devices_btn = QPushButton("✅ 全选设备")
        self.select_all_devices_btn.clicked.connect(self.select_all_devices)
        self.select_all_devices_btn.setStyleSheet(button_style)
        device_buttons.addWidget(self.select_all_devices_btn)
        
        self.deselect_all_devices_btn = QPushButton("❌ 取消全选")
        self.deselect_all_devices_btn.clicked.connect(self.deselect_all_devices)
        self.deselect_all_devices_btn.setStyleSheet(button_style)
        device_buttons.addWidget(self.deselect_all_devices_btn)
        
        device_buttons.addStretch()
        device_layout.addLayout(device_buttons)
        
        # 设备列表
        self.device_list = QListWidget()
        self.device_list.setAlternatingRowColors(True)
        device_layout.addWidget(self.device_list)
        
        layout.addWidget(device_group)
        
        # 安装选项组
        options_group = QGroupBox("⚙️ 安装选项")
        options_layout = QGridLayout(options_group)
        
        # 安装选项
        self.replace_existing = QCheckBox("替换现有应用 (-r)")
        self.replace_existing.setChecked(True)
        self.replace_existing.setToolTip("如果应用已安装，将替换现有版本")
        options_layout.addWidget(self.replace_existing, 0, 0)
        
        self.allow_downgrade = QCheckBox("允许降级 (-d)")
        self.allow_downgrade.setToolTip("允许安装较低版本的应用")
        options_layout.addWidget(self.allow_downgrade, 0, 1)
        
        self.grant_permissions = QCheckBox("授予所有权限 (-g)")
        self.grant_permissions.setToolTip("自动授予应用所需的所有权限")
        options_layout.addWidget(self.grant_permissions, 1, 0)
        
        self.install_on_sd = QCheckBox("安装到SD卡 (-s)")
        self.install_on_sd.setToolTip("将应用安装到外部存储")
        options_layout.addWidget(self.install_on_sd, 1, 1)
        
        # 超时设置
        options_layout.addWidget(QLabel("安装超时:"), 2, 0)
        self.timeout_spinbox = QSpinBox()
        self.timeout_spinbox.setRange(60, 600)
        self.timeout_spinbox.setValue(300)
        self.timeout_spinbox.setSuffix(" 秒")
        self.timeout_spinbox.setToolTip("单个APK的安装超时时间")
        options_layout.addWidget(self.timeout_spinbox, 2, 1)
        
        layout.addWidget(options_group)
        
        return widget
    
    def create_install_tab(self):
        """创建安装管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 安装状态组
        status_group = QGroupBox("📊 安装状态")
        status_layout = QVBoxLayout(status_group)
        
        # 总体进度
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("总体进度:"))
        
        self.overall_progress = QProgressBar()
        self.overall_progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                text-align: center;
                font-weight: bold;
                background-color: #ecf0f1;
            }
            QProgressBar::chunk {
                background: linear-gradient(to right, #3498db, #2980b9);
                border-radius: 6px;
            }
        """)
        progress_layout.addWidget(self.overall_progress)
        
        status_layout.addLayout(progress_layout)
        
        # 安装状态表格
        self.status_table = QTableWidget()
        self.status_table.setColumnCount(4)
        self.status_table.setHorizontalHeaderLabels([
            "设备", "APK文件", "状态", "进度"
        ])
        
        # 设置表格属性
        header = self.status_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.status_table.setAlternatingRowColors(True)
        self.status_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        status_layout.addWidget(self.status_table)
        
        layout.addWidget(status_group)
        
        return widget
    
    def create_log_tab(self):
        """创建日志标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 日志控制组
        log_control_group = QGroupBox("📋 安装日志")
        log_control_layout = QVBoxLayout(log_control_group)
        
        # 日志控制按钮
        log_buttons = QHBoxLayout()
        
        button_style = """
            QPushButton {
                background-color: white;
                color: #333333;
                border: 1px solid #dee2e6;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 500;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #f8f9fa;
                border-color: #4a90e2;
            }
            QPushButton:pressed {
                background-color: #e9ecef;
            }
        """
        
        self.clear_log_btn = QPushButton("🗑 清空日志")
        self.clear_log_btn.clicked.connect(self.clear_log)
        self.clear_log_btn.setStyleSheet(button_style)
        log_buttons.addWidget(self.clear_log_btn)
        
        self.save_log_btn = QPushButton("💾 保存日志")
        self.save_log_btn.clicked.connect(self.save_log)
        self.save_log_btn.setStyleSheet(button_style)
        log_buttons.addWidget(self.save_log_btn)
        
        log_buttons.addStretch()
        log_control_layout.addLayout(log_buttons)
        
        # 日志显示
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Consolas", 10))
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: #2c3e50;
                color: #ecf0f1;
                border: 1px solid #34495e;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        log_control_layout.addWidget(self.log_display)
        
        layout.addWidget(log_control_group)
        
        return widget
    
    def select_apk_files(self):
        """选择APK文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择APK文件", "", 
            "Android APK Files (*.apk);;All Files (*)"
        )
        
        if files:
            self.add_apk_files(files)
    
    def select_apk_folder(self):
        """选择包含APK的文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择包含APK文件的文件夹")
        
        if folder:
            # 搜索文件夹中的所有APK文件
            apk_files = []
            for root, dirs, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith('.apk'):
                        apk_files.append(os.path.join(root, file))
            
            if apk_files:
                self.add_apk_files(apk_files)
            else:
                QMessageBox.information(self, "提示", "所选文件夹中没有找到APK文件！")
    
    def add_apk_files(self, files: List[str]):
        """添加APK文件到列表"""
        for file_path in files:
            if file_path not in self.selected_apks:
                self.selected_apks.append(file_path)
        
        self.update_apk_table()
        self.update_stats()
    
    def update_apk_table(self):
        """更新APK表格显示"""
        self.apk_table.setRowCount(len(self.selected_apks))
        
        for row, apk_file in enumerate(self.selected_apks):
            # 获取APK信息
            apk_info = APKInfo(apk_file)
            
            # 选择复选框
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(self.update_stats)
            self.apk_table.setCellWidget(row, 0, checkbox)
            
            # 文件名
            self.apk_table.setItem(row, 1, QTableWidgetItem(apk_info.file_name))
            
            # 应用名
            self.apk_table.setItem(row, 2, QTableWidgetItem(apk_info.app_name or "未知"))
            
            # 包名
            self.apk_table.setItem(row, 3, QTableWidgetItem(apk_info.package_name or "未知"))
            
            # 版本信息
            version_text = apk_info.version_name or "未知"
            if apk_info.version_code:
                version_text += f" ({apk_info.version_code})"
            self.apk_table.setItem(row, 4, QTableWidgetItem(version_text))
            
            # 文件大小
            self.apk_table.setItem(row, 5, QTableWidgetItem(apk_info.file_size))
    
    def clear_apk_list(self):
        """清空APK列表"""
        self.selected_apks.clear()
        self.apk_table.setRowCount(0)
        self.update_stats()
    
    def refresh_devices(self):
        """刷新设备列表"""
        self.device_list.clear()
        
        try:
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # 跳过标题行
                
                for line in lines:
                    if line.strip() and 'device' in line:
                        device_id = line.split()[0]
                        
                        # 获取设备信息
                        device_info = self.get_device_info(device_id)
                        
                        # 创建设备项
                        item = QListWidgetItem(f"📱 {device_info}")
                        item.setData(Qt.UserRole, device_id)
                        item.setCheckState(Qt.Unchecked)
                        
                        self.device_list.addItem(item)
                
                if self.device_list.count() == 0:
                    item = QListWidgetItem("❌ 没有连接的设备")
                    item.setFlags(Qt.NoItemFlags)
                    self.device_list.addItem(item)
        except:
            item = QListWidgetItem("❌ ADB不可用")
            item.setFlags(Qt.NoItemFlags)
            self.device_list.addItem(item)
        
        self.update_stats()
    
    def get_device_info(self, device_id: str) -> str:
        """获取设备信息"""
        try:
            # 获取设备型号
            result = subprocess.run(
                ["adb", "-s", device_id, "shell", "getprop", "ro.product.model"],
                capture_output=True, text=True, timeout=3
            )
            
            if result.returncode == 0:
                model = result.stdout.strip()
                return f"{model} ({device_id})"
        except:
            pass
        
        return device_id
    
    def select_all_devices(self):
        """选择所有设备"""
        for i in range(self.device_list.count()):
            item = self.device_list.item(i)
            if item.flags() != Qt.NoItemFlags:
                item.setCheckState(Qt.Checked)
        self.update_stats()
    
    def deselect_all_devices(self):
        """取消选择所有设备"""
        for i in range(self.device_list.count()):
            item = self.device_list.item(i)
            if item.flags() != Qt.NoItemFlags:
                item.setCheckState(Qt.Unchecked)
        self.update_stats()
    
    def update_stats(self):
        """更新统计信息"""
        # 计算选中的APK数量
        selected_apks = 0
        for row in range(self.apk_table.rowCount()):
            checkbox = self.apk_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                selected_apks += 1
        
        # 计算选中的设备数量
        selected_devices = 0
        for i in range(self.device_list.count()):
            item = self.device_list.item(i)
            if item and item.checkState() == Qt.Checked:
                selected_devices += 1
        
        # 更新显示
        self.stats_label.setText(f"📊 已选择 APK: {selected_apks}个, 设备: {selected_devices}个")
        
        # 更新开始安装按钮状态
        self.start_install_btn.setEnabled(selected_apks > 0 and selected_devices > 0)
    
    def start_installation(self):
        """开始安装"""
        # 获取选中的APK文件
        selected_apks = []
        for row in range(self.apk_table.rowCount()):
            checkbox = self.apk_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                selected_apks.append(self.selected_apks[row])
        
        # 获取选中的设备
        selected_devices = []
        for i in range(self.device_list.count()):
            item = self.device_list.item(i)
            if item and item.checkState() == Qt.Checked:
                device_id = item.data(Qt.UserRole)
                selected_devices.append(device_id)
        
        if not selected_apks or not selected_devices:
            QMessageBox.warning(self, "错误", "请至少选择一个APK文件和一个目标设备！")
            return
        
        # 确认安装
        total_tasks = len(selected_apks) * len(selected_devices)
        reply = QMessageBox.question(
            self, "确认安装",
            f"即将安装 {len(selected_apks)} 个APK到 {len(selected_devices)} 个设备上。\n\n"
            f"总共 {total_tasks} 个安装任务，是否继续？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # 初始化安装状态表格
        self.init_status_table(selected_apks, selected_devices)
        
        # 切换到安装管理标签页
        self.tab_widget.setCurrentIndex(2)
        
        # 启用/禁用按钮
        self.start_install_btn.setEnabled(False)
        self.stop_install_btn.setEnabled(True)
        
        # 创建并启动安装线程
        self.install_worker = InstallWorker(selected_apks, selected_devices)
        self.install_worker.progress_updated.connect(self.update_install_progress)
        self.install_worker.install_finished.connect(self.on_install_finished)
        self.install_worker.overall_progress.connect(self.overall_progress.setValue)
        self.install_worker.log_message.connect(self.add_log_message)
        self.install_worker.finished.connect(self.on_installation_complete)
        
        self.install_worker.start()
    
    def init_status_table(self, apks: List[str], devices: List[str]):
        """初始化安装状态表格"""
        total_rows = len(apks) * len(devices)
        self.status_table.setRowCount(total_rows)
        
        row = 0
        for device_id in devices:
            for apk_file in apks:
                apk_name = os.path.basename(apk_file)
                
                # 设备ID
                self.status_table.setItem(row, 0, QTableWidgetItem(device_id))
                
                # APK文件名
                self.status_table.setItem(row, 1, QTableWidgetItem(apk_name))
                
                # 状态
                self.status_table.setItem(row, 2, QTableWidgetItem("⏳ 等待中"))
                
                # 进度条
                progress = QProgressBar()
                progress.setStyleSheet("""
                    QProgressBar {
                        border: 1px solid #bdc3c7;
                        border-radius: 3px;
                        text-align: center;
                        font-size: 10px;
                    }
                    QProgressBar::chunk {
                        background-color: #3498db;
                        border-radius: 2px;
                    }
                """)
                self.status_table.setCellWidget(row, 3, progress)
                
                row += 1
    
    def update_install_progress(self, device_id: str, apk_name: str, progress: int):
        """更新安装进度"""
        # 找到对应的行
        for row in range(self.status_table.rowCount()):
            if (self.status_table.item(row, 0).text() == device_id and 
                self.status_table.item(row, 1).text() == apk_name):
                
                # 更新状态
                if progress == 0:
                    self.status_table.item(row, 2).setText("🔄 安装中")
                elif progress == 100:
                    self.status_table.item(row, 2).setText("⏳ 完成中")
                
                # 更新进度条
                progress_bar = self.status_table.cellWidget(row, 3)
                if progress_bar:
                    progress_bar.setValue(progress)
                break
    
    def on_install_finished(self, device_id: str, apk_name: str, success: bool, message: str):
        """单个安装任务完成"""
        # 找到对应的行并更新状态
        for row in range(self.status_table.rowCount()):
            if (self.status_table.item(row, 0).text() == device_id and 
                self.status_table.item(row, 1).text() == apk_name):
                
                if success:
                    self.status_table.item(row, 2).setText("✅ 成功")
                    # 设置绿色背景
                    self.status_table.item(row, 2).setBackground(QColor(200, 255, 200))
                else:
                    self.status_table.item(row, 2).setText(f"❌ 失败")
                    # 设置红色背景
                    self.status_table.item(row, 2).setBackground(QColor(255, 200, 200))
                    # 设置工具提示显示错误信息
                    self.status_table.item(row, 2).setToolTip(message)
                
                break
    
    def on_installation_complete(self):
        """所有安装任务完成"""
        self.start_install_btn.setEnabled(True)
        self.stop_install_btn.setEnabled(False)
        
        # 显示完成消息
        QMessageBox.information(self, "安装完成", "🎉 所有安装任务已完成！\n请查看安装状态和日志了解详情。")
    
    def stop_installation(self):
        """停止安装"""
        if self.install_worker and self.install_worker.isRunning():
            self.install_worker.stop()
            self.add_log_message("⏹ 用户取消了安装任务")
        
        self.start_install_btn.setEnabled(True)
        self.stop_install_btn.setEnabled(False)
    
    def add_log_message(self, message: str):
        """添加日志消息"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.log_display.append(log_entry)
        
        # 自动滚动到底部
        cursor = self.log_display.textCursor()
        cursor.movePosition(cursor.End)
        self.log_display.setTextCursor(cursor)
    
    def clear_log(self):
        """清空日志"""
        self.log_display.clear()
    
    def save_log(self):
        """保存日志"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存日志", f"apk_install_log_{time.strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.log_display.toPlainText())
                QMessageBox.information(self, "保存成功", f"日志已保存到:\n{file_path}")
            except Exception as e:
                QMessageBox.warning(self, "保存失败", f"保存日志失败:\n{str(e)}")
    
    def apply_styles(self):
        """应用样式"""
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
            
            QTabWidget::pane {
                border: 1px solid #dee2e6;
                background-color: white;
                border-radius: 8px;
            }
            
            QTabBar::tab {
                background-color: #e9ecef;
                padding: 10px 20px;
                margin: 2px;
                border-radius: 6px 6px 0 0;
                font-weight: 500;
            }
            
            QTabBar::tab:selected {
                background-color: white;
                color: #495057;
                font-weight: bold;
            }
            
            QGroupBox {
                font-weight: bold;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 15px;
                background-color: white;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px;
                color: #495057;
                background-color: white;
            }
            
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: 500;
                min-width: 120px;
            }
            
            QPushButton:hover {
                background-color: #3d7bd1;
            }
            
            QPushButton:pressed {
                background-color: #2e5ba6;
            }
            
            QPushButton:disabled {
                background-color: #6c757d;
                color: #adb5bd;
            }
            
            QTableWidget {
                border: 1px solid #dee2e6;
                border-radius: 6px;
                gridline-color: #dee2e6;
                background-color: white;
                alternate-background-color: #f8f9fa;
            }
            
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f1f3f4;
            }
            
            QTableWidget::item:selected {
                background-color: #4a90e2;
                color: white;
            }
            
            QListWidget {
                border: 1px solid #dee2e6;
                border-radius: 6px;
                background-color: white;
                alternate-background-color: #f8f9fa;
            }
            
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #f1f3f4;
            }
            
            QListWidget::item:selected {
                background-color: #4a90e2;
                color: white;
            }
            
        """)
    
    def closeEvent(self, event):
        """关闭事件处理"""
        if self.install_worker and self.install_worker.isRunning():
            reply = QMessageBox.question(
                self, "确认关闭", 
                "安装任务正在进行中，确定要关闭吗？\n关闭后安装将被中断。",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.install_worker.stop()
                self.install_worker.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()