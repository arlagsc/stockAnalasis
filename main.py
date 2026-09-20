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
    
    # 加载全局深色金融主题 QSS
    app.setStyleSheet(DARK_THEME_QSS)

    # 创建并展示主窗口
    window = MainWindow()
    window.show()

    logger.info("%s 主窗口渲染就绪，进入 Qt 事件循环。", APP_NAME)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
