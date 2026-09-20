# -*- coding: utf-8 -*-
"""自选股票池监控管理页面

提供自选股票的分组查看、实时行情刷新、标的添加与移出管理，
并支持双击直达个股深度研判。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from app.services.watchlist_service import watchlist_service

class WatchlistPage(QWidget):
    """自选股管理与监控页面"""

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
        lbl_title = QLabel("我的自选股票池")
        lbl_title.setObjectName("TitleLabel")
        lbl_sub = QLabel("关注标的实时量价跟踪与专属分组管理")
        lbl_sub.setObjectName("SubTitleLabel")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        top_bar.addLayout(title_box)
        top_bar.addStretch()

        # 分组筛选
        self.combo_group = QComboBox()
        self.combo_group.addItem("全部分组")
        self.combo_group.currentIndexChanged.connect(self.load_watchlist)
        top_bar.addWidget(QLabel("分组:"))
        top_bar.addWidget(self.combo_group)

        # 添加新自选股
        self.input_symbol = QLineEdit()
        self.input_symbol.setPlaceholderText("输入股票代码 (如 600519)")
        self.input_symbol.setFixedWidth(180)
        top_bar.addWidget(self.input_symbol)

        self.btn_add = QPushButton("加入自选")
        self.btn_add.clicked.connect(self._on_add_clicked)
        top_bar.addWidget(self.btn_add)

        self.btn_refresh = QPushButton("刷新行情")
        self.btn_refresh.clicked.connect(self.load_watchlist)
        top_bar.addWidget(self.btn_refresh)
        layout.addLayout(top_bar)

        # 2. 自选股表格
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "股票代码", "股票简称", "最新价(元)", "今日涨跌", "换手率", "所属分组", "操作"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)
        self.table.setColumnWidth(6, 140)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.table)

    def load_watchlist(self):
        """重新加载自选股数据"""
        group = self.combo_group.currentText()
        items = watchlist_service.get_watchlist_with_quotes(group_filter=group)

        self.table.setRowCount(len(items))
        for row_idx, d in enumerate(items):
            sym = str(d.get("symbol", "")).zfill(6)
            name = str(d.get("name", ""))
            price = float(d.get("close_price", 0.0))
            change = float(d.get("change_pct", 0.0))
            turnover = float(d.get("turnover_rate", 0.0))
            grp = str(d.get("group_name", "默认自选"))

            item_sym = QTableWidgetItem(sym)
            item_sym.setTextAlignment(Qt.AlignCenter)
            item_sym.setForeground(QColor("#F1F5F9"))

            item_name = QTableWidgetItem(name)
            item_name.setTextAlignment(Qt.AlignCenter)
            item_name.setForeground(QColor("#FFFFFF"))

            item_price = QTableWidgetItem(f"{price:.2f}")
            item_price.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
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

            item_to = QTableWidgetItem(f"{turnover:.2f}%")
            item_to.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_to.setForeground(QColor("#E2E8F0"))

            item_grp = QTableWidgetItem(grp)
            item_grp.setTextAlignment(Qt.AlignCenter)
            item_grp.setForeground(QColor("#CBD5E1"))

            # 操作按钮组：研判直达 + 移出自选
            action_widget = QWidget()
            act_layout = QHBoxLayout(action_widget)
            act_layout.setContentsMargins(4, 2, 4, 2)
            act_layout.setSpacing(8)
            act_layout.setAlignment(Qt.AlignCenter)

            btn_study = QPushButton("研判")
            btn_study.setFixedSize(54, 26)
            btn_study.setStyleSheet("background-color: #0284C7; color: #FFFFFF; font-weight: bold; border-radius: 4px; font-size: 12px; padding: 0px;")
            btn_study.clicked.connect(lambda _, s=sym: self.stock_selected.emit(s))

            btn_remove = QPushButton("移出")
            btn_remove.setFixedSize(54, 26)
            btn_remove.setObjectName("SecondaryButton")
            btn_remove.setStyleSheet("background-color: #1E293B; color: #CBD5E1; border: 1px solid #334155; border-radius: 4px; font-size: 12px; padding: 0px;")
            btn_remove.clicked.connect(lambda _, s=sym: self._on_remove_clicked(s))

            act_layout.addWidget(btn_study)
            act_layout.addWidget(btn_remove)

            self.table.setItem(row_idx, 0, item_sym)
            self.table.setItem(row_idx, 1, item_name)
            self.table.setItem(row_idx, 2, item_price)
            self.table.setItem(row_idx, 3, item_chg)
            self.table.setItem(row_idx, 4, item_to)
            self.table.setItem(row_idx, 5, item_grp)
            self.table.setCellWidget(row_idx, 6, action_widget)

    def _on_add_clicked(self):
        """添加自选股"""
        sym = self.input_symbol.text().strip()
        if not sym:
            return
        success = watchlist_service.add_to_watchlist(sym)
        if success:
            self.input_symbol.clear()
            self.load_watchlist()
        else:
            QMessageBox.warning(self, "提示", f"未能成功添加标的 [{sym}]，请检查代码是否正确。")

    def _on_remove_clicked(self, symbol: str):
        """移出自选股"""
        watchlist_service.remove_from_watchlist(symbol)
        self.load_watchlist()

    def _on_row_double_clicked(self, row: int, col: int):
        """双击直达研判"""
        item = self.table.item(row, 0)
        if item:
            sym = item.text().strip()
            self.selected_symbol = sym
            self.stock_selected.emit(sym)

    def get_selected_symbol(self) -> str:
        """获取当前高亮选中的自选股代码"""
        curr_row = self.table.currentRow()
        if curr_row >= 0:
            item = self.table.item(curr_row, 0)
            if item:
                return item.text().strip()
        return getattr(self, "selected_symbol", "")
