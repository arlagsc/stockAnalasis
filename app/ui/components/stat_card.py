# -*- coding: utf-8 -*-
"""数据看板统计卡片组件

提供统一规范的金融数据卡片展示，包含核心数值、
标题、涨跌状态指示以及副文本描述。
"""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QHBoxLayout
from PySide6.QtCore import Qt

class StatCard(QFrame):
    """金融指标卡片组件"""

    def __init__(self, title: str, value: str = "--", subtitle: str = "", status: str = "flat", parent=None):
        super().__init__(parent)
        self.setObjectName("CardPanel")
        self._init_ui(title, value, subtitle, status)

    def _init_ui(self, title: str, value: str, subtitle: str, status: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        # 标题
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("color: #CBD5E1; font-size: 13px; font-weight: 600;")
        layout.addWidget(self.lbl_title)

        # 主数值
        self.lbl_value = QLabel(value)
        self.lbl_value.setStyleSheet("font-size: 22px; font-weight: 800;")
        self.set_status(status)
        layout.addWidget(self.lbl_value)

        # 副标题说明
        self.lbl_subtitle = QLabel(subtitle)
        self.lbl_subtitle.setStyleSheet("color: #94A3B8; font-size: 12px;")
        layout.addWidget(self.lbl_subtitle)

    def set_data(self, value: str, subtitle: str = "", status: str = "flat"):
        """动态更新卡片数值与状态"""
        self.lbl_value.setText(value)
        if subtitle:
            self.lbl_subtitle.setText(subtitle)
        self.set_status(status)

    def set_status(self, status: str):
        """设置涨跌颜色状态: up (亮红), down (亮绿), flat (白), accent (天蓝)"""
        if status == "up":
            self.lbl_value.setStyleSheet("color: #F87171; font-size: 22px; font-weight: 800;")
        elif status == "down":
            self.lbl_value.setStyleSheet("color: #34D399; font-size: 22px; font-weight: 800;")
        elif status == "accent":
            self.lbl_value.setStyleSheet("color: #38BDF8; font-size: 22px; font-weight: 800;")
        else:
            self.lbl_value.setStyleSheet("color: #FFFFFF; font-size: 22px; font-weight: 800;")
