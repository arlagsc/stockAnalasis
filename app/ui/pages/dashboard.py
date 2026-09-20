# -*- coding: utf-8 -*-
"""全景市场行情看板页面

展示 A 股全市场宏观量价概况、涨跌分布统计，
并提供支持模糊搜索、列排序与双击穿透至个股研判的股票池网格。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
import pandas as pd

from app.ui.components.stat_card import StatCard
from app.services.data_service import data_service
from app.services.watchlist_service import watchlist_service

class DashboardPage(QWidget):
    """大盘全景看板页面"""

    # 信号：通知主窗口跳转至个股详情
    stock_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._df = pd.DataFrame()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        # 1. 顶部标题栏
        top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        lbl_title = QLabel("市场全景大盘看板")
        lbl_title.setObjectName("TitleLabel")
        lbl_sub = QLabel("A 股全市场基础行情监控与多因子快照")
        lbl_sub.setObjectName("SubTitleLabel")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        top_bar.addLayout(title_box)
        top_bar.addStretch()

        self.btn_refresh = QPushButton("同步最新行情")
        self.btn_refresh.clicked.connect(self.refresh_data)
        top_bar.addWidget(self.btn_refresh)
        layout.addLayout(top_bar)

        # 2. 统计卡片栏
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)
        self.card_total = StatCard("覆盖标的总数", "--", "支 A 股全覆盖", "accent")
        self.card_up = StatCard("今日上涨标的", "--", "上涨家数占比 --", "up")
        self.card_down = StatCard("今日下跌标的", "--", "下跌家数占比 --", "down")
        self.card_avg = StatCard("平均涨跌幅", "--", "全市场中位数", "flat")
        
        cards_layout.addWidget(self.card_total)
        cards_layout.addWidget(self.card_up)
        cards_layout.addWidget(self.card_down)
        cards_layout.addWidget(self.card_avg)
        layout.addLayout(cards_layout)

        # 3. 搜索过滤栏
        filter_bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入股票代码或简称快速过滤 (如 600519 或 茅台)...")
        self.search_input.textChanged.connect(self._on_search_changed)
        filter_bar.addWidget(self.search_input)
        layout.addLayout(filter_bar)

        # 4. 股票数据大表格
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "股票代码", "股票简称", "最新价(元)", "涨跌幅", "成交量(手)", "换手率", "市盈率(TTM)", "总市值(亿)"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.table)

    def refresh_data(self, force: bool = False):
        """重新拉取并渲染数据"""
        self._df = data_service.get_stock_universe(force_refresh=force)
        self._update_stats()
        self._render_table(self._df)

    def _update_stats(self):
        """更新顶部统计卡片"""
        if self._df.empty:
            return
        total = len(self._df)
        up_count = int((self._df["change_pct"] > 0).sum())
        down_count = int((self._df["change_pct"] < 0).sum())
        avg_pct = float(self._df["change_pct"].mean())

        self.card_total.set_data(f"{total:,}", "支 A 股数据已就绪", "accent")
        self.card_up.set_data(f"{up_count}", f"占比 {(up_count / total * 100):.1f}%", "up")
        self.card_down.set_data(f"{down_count}", f"占比 {(down_count / total * 100):.1f}%", "down")
        status = "up" if avg_pct > 0 else ("down" if avg_pct < 0 else "flat")
        self.card_avg.set_data(f"{avg_pct:+.2f}%", "全市场等权平均", status)

    def _render_table(self, df: pd.DataFrame):
        """将 DataFrame 填充渲染至表格"""
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(df))

        for row_idx, (_, row) in enumerate(df.iterrows()):
            sym = str(row.get("symbol", "")).zfill(6)
            name = str(row.get("name", ""))
            price = float(row.get("close_price", 0.0))
            change = float(row.get("change_pct", 0.0))
            vol = float(row.get("volume", 0.0))
            turnover = float(row.get("turnover_rate", 0.0))
            pe = float(row.get("pe_ratio", 0.0))
            mkt_val = float(row.get("total_market_val", 0.0))

            item_sym = QTableWidgetItem(sym)
            item_sym.setTextAlignment(Qt.AlignCenter)
            item_sym.setForeground(QColor("#F1F5F9"))

            item_name = QTableWidgetItem(name)
            item_name.setTextAlignment(Qt.AlignCenter)
            item_name.setForeground(QColor("#FFFFFF"))

            item_price = QTableWidgetItem(f"{price:.2f}")
            item_price.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            # 涨跌幅根据正负着色 (高对比度亮红亮绿与平盘亮灰)
            item_chg = QTableWidgetItem(f"{change:+.2f}%")
            item_chg.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if change > 0:
                item_chg.setForeground(QColor("#F87171"))
                item_price.setForeground(QColor("#F87171"))
            elif change < 0:
                item_chg.setForeground(QColor("#34D399"))
                item_price.setForeground(QColor("#34D399"))
            else:
                item_chg.setForeground(QColor("#CBD5E1"))
                item_price.setForeground(QColor("#CBD5E1"))

            item_vol = QTableWidgetItem(f"{vol:,.0f}")
            item_vol.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_vol.setForeground(QColor("#E2E8F0"))

            item_turnover = QTableWidgetItem(f"{turnover:.2f}%")
            item_turnover.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_turnover.setForeground(QColor("#E2E8F0"))

            item_pe = QTableWidgetItem(f"{pe:.1f}" if pe > 0 else "--")
            item_pe.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_pe.setForeground(QColor("#94A3B8") if pe <= 0 else QColor("#E2E8F0"))

            item_val = QTableWidgetItem(f"{mkt_val:.1f}")
            item_val.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_val.setForeground(QColor("#E2E8F0"))

            self.table.setItem(row_idx, 0, item_sym)
            self.table.setItem(row_idx, 1, item_name)
            self.table.setItem(row_idx, 2, item_price)
            self.table.setItem(row_idx, 3, item_chg)
            self.table.setItem(row_idx, 4, item_vol)
            self.table.setItem(row_idx, 5, item_turnover)
            self.table.setItem(row_idx, 6, item_pe)
            self.table.setItem(row_idx, 7, item_val)

        self.table.setSortingEnabled(True)

    def _on_search_changed(self, text: str):
        """搜索框过滤"""
        if self._df.empty:
            return
        query = text.strip()
        if not query:
            self._render_table(self._df)
            return
        filtered = self._df[
            self._df["symbol"].str.contains(query, case=False) |
            self._df["name"].str.contains(query, case=False)
        ]
        self._render_table(filtered)

    def _on_row_double_clicked(self, row: int, col: int):
        """双击表格行穿透打开个股深度研判"""
        item = self.table.item(row, 0)
        if item:
            symbol = item.text().strip()
            self.stock_selected.emit(symbol)
