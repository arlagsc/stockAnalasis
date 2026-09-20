# -*- coding: utf-8 -*-
"""主应用程序窗口框架

提供深色侧边栏导航、响应式页面堆栈 (QStackedWidget) 切换、
多业务页面之间的事件信号联动以及全局状态条显示。
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QStackedWidget, QLabel, QFrame, QStatusBar
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon

from app.core.config import config, APP_NAME, APP_VERSION
from app.ui.pages.dashboard import DashboardPage
from app.ui.pages.watchlist import WatchlistPage
from app.ui.pages.screener import ScreenerPage
from app.ui.pages.recommend import RecommendPage
from app.ui.pages.stock_detail import StockDetailPage
from app.ui.pages.settings import SettingsPage

class MainWindow(QMainWindow):
    """主窗口应用程序容器"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — 股票智能分析与推荐终端 v{APP_VERSION}")
        self.resize(1280, 820)
        self.setMinimumSize(1024, 680)

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        # 主体中央 Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. 左侧导航侧边栏
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(200)
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(8, 20, 8, 16)
        side_layout.setSpacing(4)

        # 软件品牌 Title
        brand_box = QVBoxLayout()
        brand_box.setContentsMargins(12, 0, 12, 16)
        lbl_app = QLabel("📈 StockAI")
        lbl_app.setStyleSheet("font-size: 20px; font-weight: 800; color: #38BDF8;")
        lbl_ver = QLabel(f"智能分析终端 v{APP_VERSION}")
        lbl_ver.setStyleSheet("font-size: 11px; color: #64748B;")
        brand_box.addWidget(lbl_app)
        brand_box.addWidget(lbl_ver)
        side_layout.addLayout(brand_box)

        # 导航按钮组
        self.nav_buttons = []
        nav_items = [
            ("📊  大盘看板", 0),
            ("⭐  我的自选", 1),
            ("⚡  智能筛选", 2),
            ("🎯  精选推荐", 3),
            ("🔍  个股研判", 4),
            ("⚙️  系统设置", 5),
        ]
        for title, index in nav_items:
            btn = QPushButton(title)
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, idx=index: self.switch_page(idx))
            side_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        side_layout.addStretch()
        main_layout.addWidget(self.sidebar)

        # 2. 右侧页面堆栈
        self.stacked_widget = QStackedWidget()
        
        self.page_dashboard = DashboardPage()
        self.page_watchlist = WatchlistPage()
        self.page_screener = ScreenerPage()
        self.page_recommend = RecommendPage()
        self.page_stock_detail = StockDetailPage()
        self.page_settings = SettingsPage()

        self.stacked_widget.addWidget(self.page_dashboard)    # 0
        self.stacked_widget.addWidget(self.page_watchlist)    # 1
        self.stacked_widget.addWidget(self.page_screener)     # 2
        self.stacked_widget.addWidget(self.page_recommend)    # 3
        self.stacked_widget.addWidget(self.page_stock_detail) # 4
        self.stacked_widget.addWidget(self.page_settings)     # 5

        main_layout.addWidget(self.stacked_widget)

        # 3. 底部状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage(f"就绪 | 当前模型后端: {config.current_provider_name} | 数据源: AkShare 混合缓存 | 仅供研究参考，不构成投资建议")

        # 默认选中第一页
        self.switch_page(0)

    def _connect_signals(self):
        """连接各个页面之间的交互与联动信号"""
        # 大盘双击 -> 跳转个股详情
        self.page_dashboard.stock_selected.connect(self._navigate_to_stock_detail)
        # 自选双击 -> 跳转个股详情
        self.page_watchlist.stock_selected.connect(self._navigate_to_stock_detail)
        # 筛选双击 -> 跳转个股详情
        self.page_screener.stock_selected.connect(self._navigate_to_stock_detail)
        # 推荐卡片 -> 跳转个股详情
        self.page_recommend.stock_selected.connect(self._navigate_to_stock_detail)

    def switch_page(self, index: int):
        """切换显示的视图页面并高亮对应侧边栏按钮"""
        self.stacked_widget.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

        # 触发页面按需更新
        if index == 0:
            self.page_dashboard.refresh_data()
        elif index == 1:
            self.page_watchlist.load_watchlist()
        elif index == 3:
            # 精选推荐页面自动初始化
            pass

    def _navigate_to_stock_detail(self, symbol: str):
        """穿透跳转至个股研判页面"""
        self.switch_page(4)
        self.page_stock_detail.load_stock(symbol)
