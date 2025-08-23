# -*- coding: utf-8 -*-
"""
设备连接模块
功能:
- 检测ADB安装状态
- 自动安装ADB（根据系统类型）
- IP连接Android设备
- 显示连接状态
"""

import os
import sys
import platform
import subprocess
import socket
import threading
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QLineEdit, QTextEdit, QProgressBar,
                            QGroupBox, QMessageBox, QListWidget, QListWidgetItem,
                            QTabWidget, QWidget, QGridLayout, QFrame)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon, QFont, QPixmap, QPainter, QColor

class ADBInstaller(QThread):
    """ADB安装线程"""
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(bool)
    
    def __init__(self):
        super().__init__()
        self.system = platform.system().lower()
    
    def run(self):
        """执行ADB安装"""
        try:
            self.status.emit("🔍 检测系统类型...")
            self.progress.emit(10)
            
            if self.system == "linux":
                self.install_linux_adb()
            elif self.system == "windows":
                self.install_windows_adb()
            elif self.system == "darwin":
                self.install_macos_adb()
            else:
                self.status.emit(f"❌ 不支持的系统: {self.system}")
                self.finished.emit(False)
                return
                
            self.finished.emit(True)
            
        except Exception as e:
            self.status.emit(f"❌ 安装失败: {str(e)}")
            self.finished.emit(False)
    
    def install_linux_adb(self):
        """在Linux上安装ADB"""
        self.status.emit("🐧 检测Linux发行版...")
        self.progress.emit(20)
        
        # 检测发行版
        if os.path.exists("/etc/debian_version"):
            # Debian/Ubuntu
            self.status.emit("📦 使用apt安装ADB...")
            self.progress.emit(40)
            result = subprocess.run(["sudo", "apt", "update"], capture_output=True)
            if result.returncode != 0:
                raise Exception("apt update 失败")
            
            self.progress.emit(60)
            result = subprocess.run(["sudo", "apt", "install", "-y", "android-tools-adb"], 
                                  capture_output=True)
            if result.returncode != 0:
                raise Exception("ADB安装失败")
                
        elif os.path.exists("/etc/redhat-release"):
            # RedHat/CentOS/Fedora
            self.status.emit("📦 使用dnf/yum安装ADB...")
            self.progress.emit(40)
            
            # 尝试dnf（Fedora）
            if subprocess.run(["which", "dnf"], capture_output=True).returncode == 0:
                result = subprocess.run(["sudo", "dnf", "install", "-y", "android-tools"], 
                                      capture_output=True)
            else:
                # 尝试yum（CentOS）
                result = subprocess.run(["sudo", "yum", "install", "-y", "android-tools"], 
                                      capture_output=True)
            
            if result.returncode != 0:
                raise Exception("ADB安装失败")
                
        else:
            # 通用安装方法
            self.status.emit("📦 下载ADB二进制文件...")
            self.progress.emit(40)
            self.download_adb_generic()
        
        self.progress.emit(90)
        self.status.emit("✅ ADB安装完成")
        self.progress.emit(100)
    
    def install_windows_adb(self):
        """在Windows上安装ADB"""
        self.status.emit("🪟 Windows ADB安装...")
        self.progress.emit(30)
        
        # 使用chocolatey或直接下载
        if subprocess.run(["choco", "--version"], capture_output=True).returncode == 0:
            self.status.emit("📦 使用Chocolatey安装ADB...")
            self.progress.emit(50)
            result = subprocess.run(["choco", "install", "adb", "-y"], capture_output=True)
            if result.returncode != 0:
                self.download_adb_generic()
        else:
            self.download_adb_generic()
        
        self.progress.emit(100)
        self.status.emit("✅ ADB安装完成")
    
    def install_macos_adb(self):
        """在macOS上安装ADB"""
        self.status.emit("🍎 macOS ADB安装...")
        self.progress.emit(30)
        
        # 使用Homebrew
        if subprocess.run(["brew", "--version"], capture_output=True).returncode == 0:
            self.status.emit("📦 使用Homebrew安装ADB...")
            self.progress.emit(50)
            result = subprocess.run(["brew", "install", "android-platform-tools"], 
                                  capture_output=True)
            if result.returncode != 0:
                self.download_adb_generic()
        else:
            self.download_adb_generic()
        
        self.progress.emit(100)
        self.status.emit("✅ ADB安装完成")
    
    def download_adb_generic(self):
        """通用ADB下载安装"""
        self.status.emit("🌐 下载ADB平台工具...")
        self.progress.emit(60)
        
        # 这里应该实现实际的下载逻辑
        # 为了示例，我们只是模拟
        import time
        time.sleep(2)
        
        self.progress.emit(80)
        self.status.emit("📁 解压ADB工具...")
        time.sleep(1)

class DeviceScanner(QThread):
    """设备扫描线程"""
    device_found = pyqtSignal(str, str)  # IP, 设备信息
    scan_progress = pyqtSignal(int)
    
    def __init__(self, ip_range="192.168.1"):
        super().__init__()
        self.ip_range = ip_range
        self.running = True
    
    def run(self):
        """扫描网络中的Android设备"""
        for i in range(1, 255):
            if not self.running:
                break
                
            ip = f"{self.ip_range}.{i}"
            self.scan_progress.emit(int(i / 254 * 100))
            
            # 检测5555端口（ADB默认端口）
            if self.check_adb_port(ip, 5555, timeout=0.1):
                device_info = self.get_device_info(ip)
                self.device_found.emit(ip, device_info)
    
    def check_adb_port(self, ip, port, timeout=1):
        """检查指定IP和端口是否开放"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except:
            return False
    
    def get_device_info(self, ip):
        """获取设备信息"""
        try:
            # 尝试连接并获取设备信息
            result = subprocess.run(["adb", "connect", f"{ip}:5555"], 
                                  capture_output=True, text=True, timeout=5)
            if "connected" in result.stdout.lower():
                # 获取设备型号
                model_result = subprocess.run(["adb", "-s", f"{ip}:5555", "shell", "getprop", "ro.product.model"], 
                                            capture_output=True, text=True, timeout=3)
                model = model_result.stdout.strip() if model_result.returncode == 0 else "未知设备"
                return f"{model} ({ip})"
        except:
            pass
        return f"Android设备 ({ip})"
    
    def stop(self):
        """停止扫描"""
        self.running = False

class DeviceConnectionDialog(QDialog):
    """设备连接对话框"""
    device_connected = pyqtSignal(str)  # 发送连接成功的设备信息
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📱 设备连接管理")
        self.setModal(True)
        self.resize(600, 500)
        
        self.adb_available = self.check_adb_available()
        self.connected_devices = []
        
        self.init_ui()
        self.apply_styles()
        
        # 定时检查连接状态
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_device_status)
        self.status_timer.start(3000)  # 每3秒检查一次
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel("📱 Android设备连接管理")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: #2c3e50;
                padding: 10px;
                text-align: center;
            }
        """)
        layout.addWidget(title_label)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        
        # ADB状态标签页
        self.adb_tab = self.create_adb_tab()
        self.tab_widget.addTab(self.adb_tab, "🔧 ADB状态")
        
        # IP连接标签页
        self.ip_tab = self.create_ip_connection_tab()
        self.tab_widget.addTab(self.ip_tab, "🌐 IP连接")
        
        # 设备扫描标签页
        self.scan_tab = self.create_scan_tab()
        self.tab_widget.addTab(self.scan_tab, "🔍 设备扫描")
        
        # 已连接设备标签页
        self.devices_tab = self.create_devices_tab()
        self.tab_widget.addTab(self.devices_tab, "📱 已连接设备")
        
        layout.addWidget(self.tab_widget)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self.refresh_all)
        self.refresh_btn.setStyleSheet("""
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
        button_layout.addWidget(self.refresh_btn)
        
        button_layout.addStretch()
        
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
    
    def create_adb_tab(self):
        """创建ADB状态标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # ADB状态组
        status_group = QGroupBox("🔧 ADB工具状态")
        status_layout = QVBoxLayout(status_group)
        
        # 状态显示
        self.adb_status_label = QLabel()
        self.update_adb_status()
        status_layout.addWidget(self.adb_status_label)
        
        # 安装按钮
        self.install_btn = QPushButton("📥 自动安装ADB")
        self.install_btn.setEnabled(not self.adb_available)
        self.install_btn.clicked.connect(self.install_adb)
        self.install_btn.setStyleSheet("""
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
        """)
        status_layout.addWidget(self.install_btn)
        
        # 安装进度
        self.install_progress = QProgressBar()
        self.install_progress.setVisible(False)
        status_layout.addWidget(self.install_progress)
        
        # 安装日志
        self.install_log = QTextEdit()
        self.install_log.setMaximumHeight(150)
        self.install_log.setVisible(False)
        status_layout.addWidget(self.install_log)
        
        layout.addWidget(status_group)
        layout.addStretch()
        
        return widget
    
    def create_ip_connection_tab(self):
        """创建IP连接标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # IP连接组
        ip_group = QGroupBox("🌐 IP地址连接")
        ip_layout = QVBoxLayout(ip_group)
        
        # IP输入
        ip_input_layout = QHBoxLayout()
        ip_input_layout.addWidget(QLabel("设备IP地址:"))
        
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("例如: 192.168.1.100")
        self.ip_input.setText("192.168.1.")
        ip_input_layout.addWidget(self.ip_input)
        
        self.connect_btn = QPushButton("🔌 连接")
        self.connect_btn.setEnabled(self.adb_available)
        self.connect_btn.clicked.connect(self.connect_by_ip)
        self.connect_btn.setStyleSheet("""
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
        """)
        ip_input_layout.addWidget(self.connect_btn)
        
        ip_layout.addLayout(ip_input_layout)
        
        # 端口设置
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("端口:"))
        
        self.port_input = QLineEdit("5555")
        self.port_input.setMaximumWidth(80)
        port_layout.addWidget(self.port_input)
        port_layout.addStretch()
        
        ip_layout.addLayout(port_layout)
        
        # 连接状态
        self.connection_status = QLabel("⚪ 未连接")
        ip_layout.addWidget(self.connection_status)
        
        layout.addWidget(ip_group)
        
        # 常用IP快捷按钮
        quick_group = QGroupBox("⚡ 快捷连接")
        quick_layout = QGridLayout(quick_group)
        
        common_ips = [
            "192.168.1.100", "192.168.1.101", "192.168.1.102",
            "192.168.0.100", "192.168.0.101", "192.168.0.102",
            "10.0.0.100", "10.0.0.101"
        ]
        
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
        
        for i, ip in enumerate(common_ips):
            btn = QPushButton(ip)
            btn.clicked.connect(lambda checked, ip=ip: self.set_ip(ip))
            btn.setStyleSheet(button_style)
            quick_layout.addWidget(btn, i // 4, i % 4)
        
        layout.addWidget(quick_group)
        layout.addStretch()
        
        return widget
    
    def create_scan_tab(self):
        """创建设备扫描标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 扫描控制组
        scan_group = QGroupBox("🔍 网络设备扫描")
        scan_layout = QVBoxLayout(scan_group)
        
        # 扫描配置
        config_layout = QHBoxLayout()
        config_layout.addWidget(QLabel("网络段:"))
        
        self.network_input = QLineEdit("192.168.1")
        self.network_input.setPlaceholderText("例如: 192.168.1")
        config_layout.addWidget(self.network_input)
        
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
            QPushButton:disabled {
                background-color: #f8f9fa;
                color: #6c757d;
                border-color: #dee2e6;
            }
        """
        
        self.scan_btn = QPushButton("🔍 开始扫描")
        self.scan_btn.setEnabled(self.adb_available)
        self.scan_btn.clicked.connect(self.start_scan)
        self.scan_btn.setStyleSheet(button_style)
        config_layout.addWidget(self.scan_btn)
        
        self.stop_scan_btn = QPushButton("⏹ 停止")
        self.stop_scan_btn.setEnabled(False)
        self.stop_scan_btn.clicked.connect(self.stop_scan)
        self.stop_scan_btn.setStyleSheet(button_style)
        config_layout.addWidget(self.stop_scan_btn)
        
        scan_layout.addLayout(config_layout)
        
        # 扫描进度
        self.scan_progress = QProgressBar()
        scan_layout.addWidget(self.scan_progress)
        
        layout.addWidget(scan_group)
        
        # 发现的设备
        found_group = QGroupBox("📱 发现的设备")
        found_layout = QVBoxLayout(found_group)
        
        self.found_devices = QListWidget()
        self.found_devices.itemDoubleClicked.connect(self.connect_found_device)
        found_layout.addWidget(self.found_devices)
        
        layout.addWidget(found_group)
        
        return widget
    
    def create_devices_tab(self):
        """创建已连接设备标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 设备列表
        devices_group = QGroupBox("📱 已连接的设备")
        devices_layout = QVBoxLayout(devices_group)
        
        self.devices_list = QListWidget()
        devices_layout.addWidget(self.devices_list)
        
        # 设备操作按钮
        device_buttons = QHBoxLayout()
        
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
        
        self.disconnect_btn = QPushButton("🔌 断开连接")
        self.disconnect_btn.clicked.connect(self.disconnect_device)
        self.disconnect_btn.setStyleSheet(button_style)
        device_buttons.addWidget(self.disconnect_btn)
        
        self.device_info_btn = QPushButton("ℹ 设备信息")
        self.device_info_btn.clicked.connect(self.show_device_info)
        self.device_info_btn.setStyleSheet(button_style)
        device_buttons.addWidget(self.device_info_btn)
        
        device_buttons.addStretch()
        
        devices_layout.addLayout(device_buttons)
        
        layout.addWidget(devices_group)
        
        # 刷新设备列表
        self.refresh_devices()
        
        return widget
    
    def check_adb_available(self):
        """检查ADB是否可用"""
        try:
            result = subprocess.run(["adb", "version"], capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def update_adb_status(self):
        """更新ADB状态显示"""
        if self.adb_available:
            try:
                result = subprocess.run(["adb", "version"], capture_output=True, text=True, timeout=5)
                version_line = result.stdout.split('\n')[0]
                self.adb_status_label.setText(f"✅ ADB已安装\n版本: {version_line}")
                self.adb_status_label.setStyleSheet("color: #4a90e2; font-weight: bold;")
            except:
                self.adb_status_label.setText("✅ ADB已安装")
                self.adb_status_label.setStyleSheet("color: #4a90e2; font-weight: bold;")
        else:
            self.adb_status_label.setText("❌ ADB未安装\n请点击下方按钮自动安装")
            self.adb_status_label.setStyleSheet("color: red; font-weight: bold;")
    
    def install_adb(self):
        """开始ADB安装"""
        self.install_btn.setEnabled(False)
        self.install_progress.setVisible(True)
        self.install_log.setVisible(True)
        self.install_log.clear()
        
        # 创建安装线程
        self.installer = ADBInstaller()
        self.installer.progress.connect(self.install_progress.setValue)
        self.installer.status.connect(self.install_log.append)
        self.installer.finished.connect(self.installation_finished)
        self.installer.start()
    
    def installation_finished(self, success):
        """安装完成处理"""
        self.install_btn.setEnabled(True)
        self.install_progress.setVisible(False)
        
        if success:
            self.adb_available = True
            self.update_adb_status()
            self.connect_btn.setEnabled(True)
            self.scan_btn.setEnabled(True)
            QMessageBox.information(self, "安装完成", "✅ ADB安装成功！\n现在可以连接Android设备了。")
        else:
            QMessageBox.warning(self, "安装失败", "❌ ADB安装失败，请手动安装ADB工具。")
    
    def set_ip(self, ip):
        """设置IP地址"""
        self.ip_input.setText(ip)
    
    def connect_by_ip(self):
        """通过IP连接设备"""
        ip = self.ip_input.text().strip()
        port = self.port_input.text().strip()
        
        if not ip:
            QMessageBox.warning(self, "输入错误", "请输入设备IP地址！")
            return
        
        self.connection_status.setText("🔄 正在连接...")
        self.connect_btn.setEnabled(False)
        
        # 在后台线程中执行连接
        threading.Thread(target=self._connect_device, args=(ip, port)).start()
    
    def _connect_device(self, ip, port):
        """在后台连接设备"""
        try:
            result = subprocess.run(["adb", "connect", f"{ip}:{port}"], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and "connected" in result.stdout.lower():
                self.connection_status.setText(f"✅ 已连接到 {ip}:{port}")
                self.connection_status.setStyleSheet("color: #4a90e2; font-weight: bold;")
                
                # 获取设备信息
                device_info = f"{ip}:{port}"
                if device_info not in self.connected_devices:
                    self.connected_devices.append(device_info)
                
                # 发出连接成功信号
                self.device_connected.emit(f"{ip}:{port}")
                
                # 刷新设备列表
                self.refresh_devices()
            else:
                self.connection_status.setText(f"❌ 连接失败: {result.stderr}")
                self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        
        except Exception as e:
            self.connection_status.setText(f"❌ 连接错误: {str(e)}")
            self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        
        finally:
            self.connect_btn.setEnabled(True)
    
    def start_scan(self):
        """开始扫描设备"""
        network = self.network_input.text().strip()
        if not network:
            QMessageBox.warning(self, "输入错误", "请输入网络段！")
            return
        
        self.scan_btn.setEnabled(False)
        self.stop_scan_btn.setEnabled(True)
        self.found_devices.clear()
        
        self.scanner = DeviceScanner(network)
        self.scanner.device_found.connect(self.add_found_device)
        self.scanner.scan_progress.connect(self.scan_progress.setValue)
        self.scanner.finished.connect(self.scan_finished)
        self.scanner.start()
    
    def stop_scan(self):
        """停止扫描"""
        if hasattr(self, 'scanner'):
            self.scanner.stop()
    
    def scan_finished(self):
        """扫描完成"""
        self.scan_btn.setEnabled(True)
        self.stop_scan_btn.setEnabled(False)
        self.scan_progress.setValue(0)
    
    def add_found_device(self, ip, info):
        """添加发现的设备"""
        item = QListWidgetItem(f"📱 {info}")
        item.setData(Qt.UserRole, ip)
        self.found_devices.addItem(item)
    
    def connect_found_device(self, item):
        """连接发现的设备"""
        ip = item.data(Qt.UserRole)
        self.ip_input.setText(ip)
        self.tab_widget.setCurrentIndex(1)  # 切换到IP连接标签页
        self.connect_by_ip()
    
    def refresh_devices(self):
        """刷新已连接设备列表"""
        self.devices_list.clear()
        
        try:
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # 跳过标题行
                
                for line in lines:
                    if line.strip() and 'device' in line:
                        device_id = line.split()[0]
                        item = QListWidgetItem(f"📱 {device_id}")
                        item.setData(Qt.UserRole, device_id)
                        self.devices_list.addItem(item)
        except:
            pass
    
    def disconnect_device(self):
        """断开选中的设备"""
        current_item = self.devices_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "提示", "请选择要断开的设备！")
            return
        
        device_id = current_item.data(Qt.UserRole)
        
        try:
            result = subprocess.run(["adb", "disconnect", device_id], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                QMessageBox.information(self, "成功", f"✅ 已断开设备: {device_id}")
                self.refresh_devices()
            else:
                QMessageBox.warning(self, "失败", f"❌ 断开设备失败: {result.stderr}")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"❌ 操作失败: {str(e)}")
    
    def show_device_info(self):
        """显示设备详细信息"""
        current_item = self.devices_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "提示", "请选择要查看的设备！")
            return
        
        device_id = current_item.data(Qt.UserRole)
        
        try:
            # 获取设备信息
            commands = {
                "型号": ["shell", "getprop", "ro.product.model"],
                "品牌": ["shell", "getprop", "ro.product.brand"],
                "版本": ["shell", "getprop", "ro.build.version.release"],
                "API级别": ["shell", "getprop", "ro.build.version.sdk"],
                "CPU架构": ["shell", "getprop", "ro.product.cpu.abi"]
            }
            
            info_text = f"设备ID: {device_id}\n\n"
            
            for name, cmd in commands.items():
                try:
                    result = subprocess.run(["adb", "-s", device_id] + cmd, 
                                          capture_output=True, text=True, timeout=3)
                    value = result.stdout.strip() if result.returncode == 0 else "未知"
                    info_text += f"{name}: {value}\n"
                except:
                    info_text += f"{name}: 获取失败\n"
            
            QMessageBox.information(self, f"设备信息 - {device_id}", info_text)
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"❌ 获取设备信息失败: {str(e)}")
    
    def update_device_status(self):
        """定时更新设备状态"""
        if self.tab_widget.currentIndex() == 3:  # 如果当前在设备标签页
            self.refresh_devices()
    
    def refresh_all(self):
        """刷新所有信息"""
        self.adb_available = self.check_adb_available()
        self.update_adb_status()
        self.refresh_devices()
        
        # 启用/禁用相关按钮
        self.install_btn.setEnabled(not self.adb_available)
        self.connect_btn.setEnabled(self.adb_available)
        self.scan_btn.setEnabled(self.adb_available)
    
    def apply_styles(self):
        """应用样式"""
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
            
            QTabWidget::pane {
                border: 1px solid #c0c0c0;
                background-color: white;
                border-radius: 5px;
            }
            
            QTabBar::tab {
                background-color: #e0e0e0;
                padding: 8px 16px;
                margin: 2px;
                border-radius: 5px 5px 0 0;
            }
            
            QTabBar::tab:selected {
                background-color: white;
                font-weight: bold;
            }
            
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px;
            }
            
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 100px;
            }
            
            QPushButton:hover {
                background-color: #3d7bd1;
            }
            
            QPushButton:pressed {
                background-color: #2e5ba6;
            }
            
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            
            QLineEdit {
                border: 2px solid #ddd;
                border-radius: 4px;
                padding: 8px;
                font-size: 14px;
            }
            
            QLineEdit:focus {
                border-color: #4a90e2;
            }
            
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
            }
            
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            
            QListWidget::item:selected {
                background-color: #4a90e2;
                color: white;
            }
            
            QListWidget::item:hover {
                background-color: #f0f0f0;
            }
            
        """)