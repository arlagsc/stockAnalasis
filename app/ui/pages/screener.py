# -*- coding: utf-8 -*-
"""智能筛选与自然语言选股页面

支持输入任意自然语言选股诉求，调度大模型编译为量化因子规则；
亦提供预设多因子量化选股策略快速执行，将全市场股票快速筛选至精选候选池。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, Signal
import pandas as pd

from app.services.screener_service import screener_service
from app.services.watchlist_service import watchlist_service

class ScreenerPage(QWidget):
    """两阶段智能筛选器页面"""

    stock_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_result_df = pd.DataFrame()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        # 1. 顶部标题
        title_box = QVBoxLayout()
        lbl_title = QLabel("两阶段智能选股筛选器")
        lbl_title.setObjectName("TitleLabel")
        lbl_sub = QLabel("支持自然语言语义理解编译 (NL-to-Filter) 与经典多因子量化快速初筛")
        lbl_sub.setObjectName("SubTitleLabel")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        layout.addLayout(title_box)

        # 2. 自然语言输入面板
        nl_panel = QFrame()
        nl_panel.setObjectName("CardPanel")
        nl_layout = QVBoxLayout(nl_panel)
        nl_layout.setContentsMargins(16, 14, 16, 14)
        nl_layout.setSpacing(10)

        lbl_input = QLabel("自然语言智能选股指令：")
        lbl_input.setStyleSheet("font-weight: 500; color: #38BDF8;")
        nl_layout.addWidget(lbl_input)

        input_box = QHBoxLayout()
        self.input_prompt = QLineEdit()
        self.input_prompt.setPlaceholderText("例如：“帮我找出市盈率低于 25 且今天涨幅大于 1.5% 的优质股票”")
        self.btn_run_nl = QPushButton("大模型解析并筛选")
        self.btn_run_nl.clicked.connect(self._on_run_nl_clicked)
        input_box.addWidget(self.input_prompt)
        input_box.addWidget(self.btn_run_nl)
        nl_layout.addLayout(input_box)

        # 预设策略快捷按钮
        preset_box = QHBoxLayout()
        lbl_preset = QLabel("常用预设策略:")
        lbl_preset.setStyleSheet("color: #94A3B8; font-size: 12px;")
        preset_box.addWidget(lbl_preset)

        for name in ["低估值稳健白马", "多头突破高弹性", "超跌潜力关注"]:
            btn = QPushButton(name)
            btn.setObjectName("SecondaryButton")
            btn.clicked.connect(lambda _, n=name: self._on_preset_clicked(n))
            preset_box.addWidget(btn)
        preset_box.addStretch()
        nl_layout.addLayout(preset_box)
        layout.addWidget(nl_panel)

        # 3. 规则解析状态与批量操作栏
        action_bar = QHBoxLayout()
        self.lbl_explanation = QLabel("当前尚未执行筛选策略")
        self.lbl_explanation.setStyleSheet("color: #94A3B8; font-size: 12px;")
        action_bar.addWidget(self.lbl_explanation)
        action_bar.addStretch()

        self.btn_batch_add = QPushButton("一键将筛选结果加入自选")
        self.btn_batch_add.setObjectName("SecondaryButton")
        self.btn_batch_add.clicked.connect(self._on_batch_add_clicked)
        action_bar.addWidget(self.btn_batch_add)
        layout.addLayout(action_bar)

        # 4. 筛选结果表格
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "股票代码", "股票简称", "最新价(元)", "今日涨跌幅", "成交量(手)", "市盈率(TTM)", "总市值(亿)"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.table)

    def _on_run_nl_clicked(self):
        """执行自然语言语义选股"""
        query = self.input_prompt.text().strip()
        if not query:
            return
        self.btn_run_nl.setEnabled(False)
        self.btn_run_nl.setText("模型解析中...")
        try:
            plan, result_df = screener_service.screen_by_natural_language(query)
            self._current_result_df = result_df
            self.lbl_explanation.setText(f"已解析规则: 【{plan.explanation}】 (命中标的: {len(result_df)} 只)")
            self._render_table(result_df)
        finally:
            self.btn_run_nl.setEnabled(True)
            self.btn_run_nl.setText("大模型解析并筛选")

    def _on_preset_clicked(self, name: str):
        """执行预设量化策略"""
        plan = screener_service.preset_strategies.get(name)
        if plan:
            result_df = screener_service.execute_filter_plan(plan)
            self._current_result_df = result_df
            self.lbl_explanation.setText(f"预设策略【{name}】: {plan.explanation} (命中标的: {len(result_df)} 只)")
            self._render_table(result_df)

    def _render_table(self, df: pd.DataFrame):
        """渲染结果"""
        self.table.setRowCount(len(df))
        for row_idx, (_, row) in enumerate(df.iterrows()):
            sym = str(row.get("symbol", "")).zfill(6)
            name = str(row.get("name", ""))
            price = float(row.get("close_price", 0.0))
            change = float(row.get("change_pct", 0.0))
            vol = float(row.get("volume", 0.0))
            pe = float(row.get("pe_ratio", 0.0))
            mkt = float(row.get("total_market_val", 0.0))

            item_sym = QTableWidgetItem(sym)
            item_sym.setTextAlignment(Qt.AlignCenter)
            item_name = QTableWidgetItem(name)
            item_name.setTextAlignment(Qt.AlignCenter)
            item_price = QTableWidgetItem(f"{price:.2f}")
            item_price.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            item_chg = QTableWidgetItem(f"{change:+.2f}%")
            item_chg.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if change > 0:
                item_chg.setForeground(Qt.red)
                item_price.setForeground(Qt.red)
            elif change < 0:
                item_chg.setForeground(Qt.green)
                item_price.setForeground(Qt.green)

            item_vol = QTableWidgetItem(f"{vol:,.0f}")
            item_vol.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_pe = QTableWidgetItem(f"{pe:.1f}" if pe > 0 else "--")
            item_pe.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_mkt = QTableWidgetItem(f"{mkt:.1f}")
            item_mkt.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            self.table.setItem(row_idx, 0, item_sym)
            self.table.setItem(row_idx, 1, item_name)
            self.table.setItem(row_idx, 2, item_price)
            self.table.setItem(row_idx, 3, item_chg)
            self.table.setItem(row_idx, 4, item_vol)
            self.table.setItem(row_idx, 5, item_pe)
            self.table.setItem(row_idx, 6, item_mkt)

    def _on_batch_add_clicked(self):
        """批量加自选"""
        if self._current_result_df.empty:
            QMessageBox.information(self, "提示", "当前无筛选结果标的可加入自选。")
            return
        count = 0
        for _, row in self._current_result_df.iterrows():
            sym = str(row.get("symbol", "")).zfill(6)
            if watchlist_service.add_to_watchlist(sym, group_name="智能筛选池"):
                count += 1
        QMessageBox.information(self, "成功", f"已成功将 {count} 只标的批量加入自选池（分组：智能筛选池）！")

    def _on_row_double_clicked(self, row: int, col: int):
        """双击直达研判"""
        item = self.table.item(row, 0)
        if item:
            self.stock_selected.emit(item.text().strip())
