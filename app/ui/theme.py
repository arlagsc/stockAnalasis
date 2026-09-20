# -*- coding: utf-8 -*-
"""金融终端深色现代主题与 QSS 样式表

为 PySide6 应用提供一致的、专业沉浸式的深色金融终端视觉体验。
支持高分屏 DPI 自适应、清晰的涨跌色彩（红涨绿跌）与层次分明的灰度层次。
"""

DARK_THEME_QSS = """
/* 全局基础设置 */
QWidget {
    background-color: #121418;
    color: #E2E8F0;
    font-family: "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
    font-size: 13px;
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
}

/* 主窗口与主背景 */
QMainWindow, QDialog {
    background-color: #0F1115;
}

/* 滚动条美化 */
QScrollBar:vertical {
    border: none;
    background: #181B20;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #334155;
    min-height: 24px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #475569;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #181B20;
    height: 8px;
    margin: 0px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #334155;
    min-width: 24px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: #475569;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* 卡片容器与面板 */
QFrame#CardPanel {
    background-color: #1A1D24;
    border: 1px solid #262B34;
    border-radius: 8px;
}

/* 导航侧边栏 */
QFrame#Sidebar {
    background-color: #16181E;
    border-right: 1px solid #232730;
}

/* 导航按钮 */
QPushButton#NavButton {
    background-color: transparent;
    color: #94A3B8;
    border: none;
    text-align: left;
    padding: 10px 16px;
    font-size: 14px;
    font-weight: 500;
    border-radius: 6px;
    margin: 2px 8px;
}
QPushButton#NavButton:hover {
    background-color: #21252E;
    color: #F1F5F9;
}
QPushButton#NavButton:checked {
    background-color: #1E293B;
    color: #38BDF8;
    border-left: 3px solid #38BDF8;
    font-weight: bold;
}

/* 标准操作按钮 */
QPushButton {
    background-color: #2563EB;
    color: #FFFFFF;
    border: none;
    padding: 7px 16px;
    border-radius: 6px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #1D4ED8;
}
QPushButton:pressed {
    background-color: #1E40AF;
}
QPushButton:disabled {
    background-color: #1E293B;
    color: #64748B;
}

/* 次级/轮廓按钮 */
QPushButton#SecondaryButton {
    background-color: #1E293B;
    color: #CBD5E1;
    border: 1px solid #334155;
}
QPushButton#SecondaryButton:hover {
    background-color: #334155;
    color: #F8FAFC;
}

/* 文本输入框与下拉选择框 */
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
    background-color: #161922;
    border: 1px solid #2C3340;
    border-radius: 6px;
    padding: 6px 12px;
    color: #FFFFFF;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid #38BDF8;
    background-color: #1C212D;
    color: #FFFFFF;
}
QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}
QComboBox QAbstractItemView {
    background-color: #161922;
    border: 1px solid #334155;
    selection-background-color: #2563EB;
    color: #FFFFFF;
}

/* 数据表格 (QTableWidget / QTableView) 终极深色高对比度防御 */
QTableWidget, QTableView {
    background-color: #0F1218;
    alternate-background-color: #171B24; /* 显式交替行：极深微灰蓝，彻底根除白色交替底！ */
    border: 1px solid #232732;
    border-radius: 6px;
    gridline-color: #1E232F;
    color: #F8FAFC;
    selection-background-color: #1D4ED8;
    selection-color: #FFFFFF;
    outline: none;
}
QTableWidget::item, QTableView::item {
    background-color: transparent;
    color: #F1F5F9;
    padding: 6px 8px;
    border: none;
}
QTableWidget::item:alternate, QTableView::item:alternate {
    background-color: #171B24;
    color: #F1F5F9;
}
QTableWidget::item:selected, QTableView::item:selected {
    background-color: #1E3A8A;
    color: #FFFFFF;
}
QTableWidget::item:hover, QTableView::item:hover {
    background-color: #222836;
    color: #FFFFFF;
}
QTableWidget QPushButton, QTableView QPushButton {
    min-height: 24px;
    max-height: 28px;
    padding: 2px 8px;
    font-size: 12px;
    border-radius: 4px;
}
QHeaderView::section {
    background-color: #161922;
    color: #CBD5E1;
    padding: 8px 6px;
    border: none;
    border-bottom: 1px solid #2B3240;
    font-weight: 600;
}
QHeaderView::section:checked {
    color: #38BDF8;
}
QTableCornerButton::section {
    background-color: #161922;
    border: none;
}

/* 标签提示与徽章 */
QLabel#TitleLabel {
    font-size: 18px;
    font-weight: bold;
    color: #F8FAFC;
}
QLabel#SubTitleLabel {
    font-size: 13px;
    color: #94A3B8;
}
QLabel#PriceUp {
    color: #EF4444; /* 红色涨 */
    font-weight: bold;
}
QLabel#PriceDown {
    color: #10B981; /* 绿色跌 */
    font-weight: bold;
}
QLabel#PriceFlat {
    color: #94A3B8;
}

/* 状态栏 */
QStatusBar {
    background-color: #121418;
    border-top: 1px solid #222630;
    color: #64748B;
    font-size: 12px;
}
"""

# 配色常量定义
COLOR_BG = "#121418"
COLOR_CARD = "#1A1D24"
COLOR_UP = "#EF4444"     # 涨 红
COLOR_DOWN = "#10B981"   # 跌 绿
COLOR_ACCENT = "#38BDF8" # 强调天蓝
COLOR_TEXT_MAIN = "#F8FAFC"
COLOR_TEXT_MUTED = "#94A3B8"
