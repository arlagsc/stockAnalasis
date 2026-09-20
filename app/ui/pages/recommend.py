# -*- coding: utf-8 -*-
"""智能精选推荐页面

基于两阶段漏斗机制，展示大模型深度精排后的优质标的，
呈现多维度综合打分、入选理由归因与风险提示卡片。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, Signal

from app.services.recommend_service import recommend_service
from app.services.watchlist_service import watchlist_service

class RecommendCard(QFrame):
    """单只股票智能推荐卡片"""

    stock_selected = Signal(str)

    def __init__(self, stock_data, parent=None):
        super().__init__(parent)
        self.setObjectName("CardPanel")
        self.stock_data = stock_data
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        # 头部：代码、名称、评分与操作
        header = QHBoxLayout()
        name_lbl = QLabel(f"{self.stock_data.name} ({self.stock_data.symbol})")
        name_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #F8FAFC;")
        header.addWidget(name_lbl)

        score_lbl = QLabel(f"综合评分: {self.stock_data.score:.0f} 分")
        score_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #38BDF8; background: #1E293B; border-radius: 4px; padding: 2px 8px;")
        header.addWidget(score_lbl)
        header.addStretch()

        btn_detail = QPushButton("深度研判")
        btn_detail.clicked.connect(lambda: self.stock_selected.emit(self.stock_data.symbol))
        header.addWidget(btn_detail)

        btn_fav = QPushButton("加入自选")
        btn_fav.setObjectName("SecondaryButton")
        btn_fav.clicked.connect(self._on_fav_clicked)
        header.addWidget(btn_fav)
        layout.addLayout(header)

        # 推荐理由列表
        reasons_box = QVBoxLayout()
        reasons_box.setSpacing(4)
        lbl_reasons_title = QLabel("核心推荐理由：")
        lbl_reasons_title.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: bold;")
        reasons_box.addWidget(lbl_reasons_title)

        for reason in self.stock_data.reasons:
            r_lbl = QLabel(f"• {reason}")
            r_lbl.setStyleSheet("color: #CBD5E1; font-size: 12px; line-height: 1.4;")
            r_lbl.setWordWrap(True)
            reasons_box.addWidget(r_lbl)
        layout.addLayout(reasons_box)

        # 风险提示
        if self.stock_data.risk_warnings:
            risk_lbl = QLabel(f"⚠️ 核心风险关注：{self.stock_data.risk_warnings}")
            risk_lbl.setStyleSheet("color: #F87171; font-size: 12px; font-style: italic;")
            risk_lbl.setWordWrap(True)
            layout.addWidget(risk_lbl)

    def _on_fav_clicked(self):
        success = watchlist_service.add_to_watchlist(self.stock_data.symbol, group_name="AI推荐池")
        if success:
            QMessageBox.information(self, "成功", f"标的 [{self.stock_data.name}] 已加入自选池（分组：AI推荐池）！")

class RecommendPage(QWidget):
    """智能精选推荐看板页面"""

    stock_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        # 1. 顶部控制栏
        top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        lbl_title = QLabel("AI 智能精选推荐看板")
        lbl_title.setObjectName("TitleLabel")
        lbl_sub = QLabel("两阶段漏斗精排模型驱动，提供可解释的入选逻辑与风险警示")
        lbl_sub.setObjectName("SubTitleLabel")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        top_bar.addLayout(title_box)
        top_bar.addStretch()

        self.btn_refresh = QPushButton("生成最新推荐")
        self.btn_refresh.clicked.connect(self.refresh_recommendations)
        top_bar.addWidget(self.btn_refresh)
        layout.addLayout(top_bar)

        # 2. 市场环境总结横幅
        self.summary_banner = QFrame()
        self.summary_banner.setObjectName("CardPanel")
        banner_layout = QVBoxLayout(self.summary_banner)
        banner_layout.setContentsMargins(16, 12, 16, 12)
        
        self.lbl_market_summary = QLabel("正在评估市场环境并生成智能精选推荐...")
        self.lbl_market_summary.setStyleSheet("color: #E2E8F0; font-size: 13px; font-weight: 500;")
        self.lbl_market_summary.setWordWrap(True)
        banner_layout.addWidget(self.lbl_market_summary)
        layout.addWidget(self.summary_banner)

        # 3. 滚动区域展示卡片流
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.card_container = QWidget()
        self.cards_layout = QVBoxLayout(self.card_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(12)
        self.cards_layout.addStretch()
        self.scroll_area.setWidget(self.card_container)
        layout.addWidget(self.scroll_area)

    def refresh_recommendations(self):
        """刷新并生成推荐"""
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("模型推理中...")
        try:
            res = recommend_service.generate_recommendations(top_n=5)
            self.lbl_market_summary.setText(f"宏观与量化研判：{res.market_summary}")

            # 清空旧卡片
            for i in reversed(range(self.cards_layout.count() - 1)):
                item = self.cards_layout.itemAt(i)
                if item and item.widget():
                    item.widget().setParent(None)

            # 插入新卡片
            for stock in res.recommended_stocks:
                card = RecommendCard(stock)
                card.stock_selected.connect(self.stock_selected.emit)
                self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
        finally:
            self.btn_refresh.setEnabled(True)
            self.btn_refresh.setText("生成最新推荐")
