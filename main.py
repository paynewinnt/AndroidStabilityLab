#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
AndroidMetrics - Modern UI Version
Performance Monitor with Beautiful Interface
"""

import sys
import os
import logging
from PyQt5.QtWidgets import QApplication, QSplashScreen
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QPainter, QFont, QColor, QLinearGradient

# Add project path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gui.modern_main_window import ModernMainWindow
from PyQt5.QtGui import QIcon

def setup_logging():
    """Setup enhanced logging configuration"""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [%(levelname)s] - %(name)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, 'androidmetrics.log')),
            logging.StreamHandler(sys.stdout)
        ]
    )

class ModernSplashScreen(QSplashScreen):
    """Custom splash screen with gradient background"""
    
    def __init__(self):
        # Create pixmap
        pixmap = QPixmap(600, 400)
        pixmap.fill(Qt.transparent)
        
        # Paint gradient background
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Create gradient
        gradient = QLinearGradient(0, 0, 600, 400)
        gradient.setColorAt(0, QColor(70, 130, 180))  # Steel Blue
        gradient.setColorAt(1, QColor(100, 149, 237))  # Cornflower Blue
        
        # Draw rounded rectangle with gradient
        painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, 600, 400, 20, 20)
        
        # Draw title
        painter.setPen(QColor(255, 255, 255))
        title_font = QFont("Microsoft YaHei", 32, QFont.Bold)
        painter.setFont(title_font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter | Qt.AlignTop, 
                        "\n\nAndroidMetrics")
        
        # Draw subtitle
        subtitle_font = QFont("Microsoft YaHei", 14)
        painter.setFont(subtitle_font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter,
                        "专业的Android性能监控解决方案")
        
        # Draw version
        version_font = QFont("Microsoft YaHei", 11)
        painter.setFont(version_font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter | Qt.AlignBottom,
                        "版本 2.0\n正在启动...\n\n")
        
        # Draw decorative elements
        painter.setPen(QColor(255, 255, 255, 100))
        painter.drawEllipse(50, 50, 100, 100)
        painter.drawEllipse(450, 250, 100, 100)
        
        painter.end()
        
        super().__init__(pixmap, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        
        # Set mask for rounded corners
        self.setMask(pixmap.mask())

def main():
    """Main entry point for modern UI"""
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("AndroidMetrics starting...")
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("AndroidMetrics")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("AndroidMetrics Team")
    
    # 设置应用图标
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icons", "androidmetrics_icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    # Set application style
    app.setStyle('Fusion')
    
    # Set default font
    default_font = QFont("Segoe UI", 11)
    app.setFont(default_font)
    
    # Set global stylesheet for dialogs
    app.setStyleSheet("""
        QFileDialog QPushButton, QMessageBox QPushButton, QProgressDialog QPushButton,
        QDialog QPushButton[text="保存"], QDialog QPushButton[text="取消"], 
        QDialog QPushButton[text="Save"], QDialog QPushButton[text="Cancel"],
        QDialog QPushButton[text="OK"], QDialog QPushButton[text="确定"],
        QDialog QPushButton[text="Yes"], QDialog QPushButton[text="No"],
        QDialog QPushButton[text="是"], QDialog QPushButton[text="否"] {
            background-color: white;
            color: #333333;
            border: 1px solid #dee2e6;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: 500;
            min-width: 80px;
        }
        QFileDialog QPushButton:hover, QMessageBox QPushButton:hover, QProgressDialog QPushButton:hover,
        QDialog QPushButton[text="保存"]:hover, QDialog QPushButton[text="取消"]:hover,
        QDialog QPushButton[text="Save"]:hover, QDialog QPushButton[text="Cancel"]:hover,
        QDialog QPushButton[text="OK"]:hover, QDialog QPushButton[text="确定"]:hover,
        QDialog QPushButton[text="Yes"]:hover, QDialog QPushButton[text="No"]:hover,
        QDialog QPushButton[text="是"]:hover, QDialog QPushButton[text="否"]:hover {
            background-color: #f8f9fa;
            border-color: #4a90e2;
        }
        QFileDialog QPushButton:pressed, QMessageBox QPushButton:pressed, QProgressDialog QPushButton:pressed,
        QDialog QPushButton[text="保存"]:pressed, QDialog QPushButton[text="取消"]:pressed,
        QDialog QPushButton[text="Save"]:pressed, QDialog QPushButton[text="Cancel"]:pressed,
        QDialog QPushButton[text="OK"]:pressed, QDialog QPushButton[text="确定"]:pressed,
        QDialog QPushButton[text="Yes"]:pressed, QDialog QPushButton[text="No"]:pressed,
        QDialog QPushButton[text="是"]:pressed, QDialog QPushButton[text="否"]:pressed {
            background-color: #e9ecef;
        }
    """)
    
    # Show splash screen
    splash = ModernSplashScreen()
    splash.show()
    app.processEvents()
    
    # Simulate loading
    loading_messages = [
        "正在初始化核心组件...",
        "正在加载配置文件...",
        "正在设置监控引擎...",
        "正在准备用户界面...",
        "准备就绪，即将启动！"
    ]
    
    for i, message in enumerate(loading_messages):
        QTimer.singleShot(i * 500, lambda msg=message: splash.showMessage(
            f"\n\nAndroidMetrics\n\n专业的Android性能监控解决方案\n\n\n\n\n\n{msg}",
            Qt.AlignCenter,
            Qt.white
        ))
        app.processEvents()
    
    # Create main window
    def show_main_window():
        global main_window
        main_window = ModernMainWindow()
        splash.finish(main_window)
        main_window.show()
        logger.info("AndroidMetrics started successfully")
    
    # Show main window after splash
    QTimer.singleShot(2500, show_main_window)
    
    # Run application
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()