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

            item_to = QTableWidgetItem(f"{turnover:.2f}%")
            item_to.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_grp = QTableWidgetItem(grp)
            item_grp.setTextAlignment(Qt.AlignCenter)

            # 操作按钮：移出自选
            btn_remove = QPushButton("移出")
            btn_remove.setObjectName("SecondaryButton")
            btn_remove.clicked.connect(lambda _, s=sym: self._on_remove_clicked(s))

            self.table.setItem(row_idx, 0, item_sym)
            self.table.setItem(row_idx, 1, item_name)
            self.table.setItem(row_idx, 2, item_price)
            self.table.setItem(row_idx, 3, item_chg)
            self.table.setItem(row_idx, 4, item_to)
            self.table.setItem(row_idx, 5, item_grp)
            self.table.setCellWidget(row_idx, 6, btn_remove)

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
            self.stock_selected.emit(item.text().strip())
