# -*- coding: utf-8 -*-
"""股票智能分析软件 — 主程序入口

初始化 Qt 应用程序上下文、加载深色金融终端样式表、
适配跨平台高分屏缩放并启动主窗口。
"""

import sys
import os
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from app.core.config import config, logger, APP_NAME
from app.ui.theme import DARK_THEME_QSS
from app.ui.main_window import MainWindow

def main():
    """应用程序启动主函数"""
    logger.info("启动 %s 客户端应用...", APP_NAME)

    # 启用高分屏支持
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    
    # 强制启用跨平台一致的 Fusion 风格并注入深色调色板，防止系统默认亮色底泄漏
    from PySide6.QtGui import QPalette, QColor
    app.setStyle("Fusion")
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor("#0F1115"))
    dark_palette.setColor(QPalette.WindowText, QColor("#F8FAFC"))
    dark_palette.setColor(QPalette.Base, QColor("#12141B"))
    dark_palette.setColor(QPalette.AlternateBase, QColor("#181C26"))  # 核心：锁定深色交替行背景
    dark_palette.setColor(QPalette.ToolTipBase, QColor("#1E293B"))
    dark_palette.setColor(QPalette.ToolTipText, QColor("#FFFFFF"))
    dark_palette.setColor(QPalette.Text, QColor("#F1F5F9"))
    dark_palette.setColor(QPalette.Button, QColor("#1E293B"))
    dark_palette.setColor(QPalette.ButtonText, QColor("#FFFFFF"))
    dark_palette.setColor(QPalette.BrightText, QColor("#EF4444"))
    dark_palette.setColor(QPalette.Link, QColor("#38BDF8"))
    dark_palette.setColor(QPalette.Highlight, QColor("#1D4ED8"))
    dark_palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(dark_palette)

    # 加载全局深色金融主题 QSS
    app.setStyleSheet(DARK_THEME_QSS)

    # 创建并展示主窗口
    window = MainWindow()
    window.show()

    logger.info("%s 主窗口渲染就绪，进入 Qt 事件循环。", APP_NAME)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
