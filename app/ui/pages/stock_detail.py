# -*- coding: utf-8 -*-
"""个股深度研判与 AI 智能诊断页面

集成 PyQtGraph 高性能 K 线图、财务指标与多维数据，
并通过后台线程实现大模型流式打字生成结构化研报（技术/基本/资金/风险四维诊断）。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QSplitter, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal
import pandas as pd

from app.core.config import logger
from app.core.database import db_manager, AnalysisReport
from app.ui.components.chart_widget import StockChartWidget
from app.services.data_service import data_service
from app.services.watchlist_service import watchlist_service
from app.ai.llm_client import llm_client
from app.ai.prompts import STOCK_ANALYSIS_SYSTEM_PROMPT, STOCK_ANALYSIS_USER_TEMPLATE
from app.ui.pages.virtual_trading import BuyDialog

class AIStreamWorker(QThread):
    """大模型流式生成异步工作线程"""

    chunk_received = Signal(str)
    finished_signal = Signal(str)

    def __init__(self, system_prompt: str, user_prompt: str):
        super().__init__()
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.full_content = ""

    def run(self):
        try:
            for chunk in llm_client.stream_chat(self.system_prompt, self.user_prompt):
                self.full_content += chunk
                self.chunk_received.emit(chunk)
            self.finished_signal.emit(self.full_content)
        except Exception as e:
            err = f"\n生成报告异常: {str(e)}"
            self.full_content += err
            self.chunk_received.emit(err)
            self.finished_signal.emit(self.full_content)

class StockDetailPage(QWidget):
    """个股深度诊断与交互研判页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_symbol = "600519"
        self._current_detail = {}
        self._worker: Optional[AIStreamWorker] = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # 1. 顶部操作栏
        top_bar = QHBoxLayout()
        self.lbl_stock_title = QLabel("贵州茅台 (600519)")
        self.lbl_stock_title.setObjectName("TitleLabel")
        top_bar.addWidget(self.lbl_stock_title)

        self.lbl_price_info = QLabel("现价: -- | 涨跌幅: -- | PE: -- | 市值: --")
        self.lbl_price_info.setStyleSheet("color: #94A3B8; font-size: 13px; margin-left: 12px;")
        top_bar.addWidget(self.lbl_price_info)
        top_bar.addStretch()

        # 代码搜索与即时切换框
        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("输入6位股票代码...")
        self.input_search.setFixedWidth(140)
        self.input_search.returnPressed.connect(self._on_search_stock)
        top_bar.addWidget(self.input_search)

        self.btn_search = QPushButton("切换")
        self.btn_search.setObjectName("SecondaryButton")
        self.btn_search.setFixedWidth(60)
        self.btn_search.clicked.connect(self._on_search_stock)
        top_bar.addWidget(self.btn_search)

        self.btn_fav = QPushButton("加入自选")
        self.btn_fav.setObjectName("SecondaryButton")
        self.btn_fav.clicked.connect(self._on_fav_toggle)
        top_bar.addWidget(self.btn_fav)

        self.btn_virtual_buy = QPushButton("💼 模拟买入")
        self.btn_virtual_buy.setObjectName("SecondaryButton")
        self.btn_virtual_buy.setStyleSheet("color: #38BDF8; font-weight: bold;")
        self.btn_virtual_buy.clicked.connect(self._on_virtual_buy)
        top_bar.addWidget(self.btn_virtual_buy)

        self.btn_ai_report = QPushButton("AI 一键深度研报")
        self.btn_ai_report.clicked.connect(self.generate_ai_report)
        top_bar.addWidget(self.btn_ai_report)
        layout.addLayout(top_bar)

        # 2. 垂直分割面板：上部为 K 线图，下部为 AI 研报控制台
        splitter = QSplitter(Qt.Vertical)

        # 上部图表容器
        chart_container = QFrame()
        chart_container.setObjectName("CardPanel")
        chart_layout = QVBoxLayout(chart_container)
        chart_layout.setContentsMargins(10, 10, 10, 10)
        self.chart_widget = StockChartWidget()
        chart_layout.addWidget(self.chart_widget)
        splitter.addWidget(chart_container)

        # 下部 AI 研报展示区域
        report_container = QFrame()
        report_container.setObjectName("CardPanel")
        report_layout = QVBoxLayout(report_container)
        report_layout.setContentsMargins(12, 10, 12, 10)
        report_layout.setSpacing(6)

        lbl_rep_title = QLabel("AI 智能研报工作台 (实时流式打字诊断)")
        lbl_rep_title.setStyleSheet("font-weight: bold; color: #38BDF8; font-size: 13px;")
        report_layout.addWidget(lbl_rep_title)

        self.txt_report = QTextEdit()
        self.txt_report.setReadOnly(True)
        self.txt_report.setPlaceholderText("点击右上角【AI 一键深度研报】按钮，大模型将基于当前量化技术面、财务基本面与资讯实时生成多维诊断报告...")
        report_layout.addWidget(self.txt_report)

        splitter.addWidget(report_container)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

    def load_stock(self, symbol: str):
        """加载展示指定股票的多维信息与 K 线"""
        self.current_symbol = str(symbol).zfill(6)
        self._current_detail = data_service.get_stock_detail(self.current_symbol)
        
        name = self._current_detail.get("name", "A股标的")
        price = float(self._current_detail.get("close_price", 0.0))
        change = float(self._current_detail.get("change_pct", 0.0))
        pe = float(self._current_detail.get("pe_ratio", 0.0))
        mkt = float(self._current_detail.get("total_market_val", 0.0))

        self.lbl_stock_title.setText(f"{name} ({self.current_symbol})")
        color_hex = "#EF4444" if change > 0 else "#10B981"
        self.lbl_price_info.setText(
            f"现价: <b style='color:{color_hex}'>{price:.2f}</b> 元 | "
            f"涨跌幅: <b style='color:{color_hex}'>{change:+.2f}%</b> | "
            f"市盈率: <b>{pe:.1f}</b> | "
            f"总市值: <b>{mkt:.1f}</b> 亿"
        )

        # 更新自选按钮文案
        in_fav = watchlist_service.is_in_watchlist(self.current_symbol)
        self.btn_fav.setText("已在自选" if in_fav else "加入自选")

        # 刷新 K 线
        kline_df = self._current_detail.get("kline_df", pd.DataFrame())
        if not kline_df.empty:
            self.chart_widget.load_kline_data(kline_df)

    def generate_ai_report(self):
        """触发大模型流式生成研报"""
        if not self._current_detail:
            self.load_stock(self.current_symbol)

        self.btn_ai_report.setEnabled(False)
        self.btn_ai_report.setText("AI 推理生成中...")
        self.txt_report.clear()

        # 组装 Prompt
        news_summary = ""
        for n in self._current_detail.get("news_list", []):
            news_summary += f"- [{n.get('time')}] {n.get('title')}: {n.get('content')}\n"

        user_prompt = STOCK_ANALYSIS_USER_TEMPLATE.format(
            name=self._current_detail.get("name", ""),
            symbol=self.current_symbol,
            close_price=self._current_detail.get("close_price", 0.0),
            change_pct=self._current_detail.get("change_pct", 0.0),
            volume=self._current_detail.get("volume", 0.0),
            turnover_rate=self._current_detail.get("turnover_rate", 0.0),
            pe_ratio=self._current_detail.get("pe_ratio", 0.0),
            pb_ratio=self._current_detail.get("pb_ratio", 0.0),
            total_market_val=self._current_detail.get("total_market_val", 0.0),
            ma5=f"{self._current_detail.get('ma5', 0.0):.2f}",
            ma10=f"{self._current_detail.get('ma10', 0.0):.2f}",
            ma20=f"{self._current_detail.get('ma20', 0.0):.2f}",
            ma60=f"{self._current_detail.get('ma60', 0.0):.2f}",
            dif=f"{self._current_detail.get('dif', 0.0):.3f}",
            dea=f"{self._current_detail.get('dea', 0.0):.3f}",
            macd=f"{self._current_detail.get('macd', 0.0):.3f}",
            rsi6=f"{self._current_detail.get('rsi6', 0.0):.1f}",
            rsi12=f"{self._current_detail.get('rsi12', 0.0):.1f}",
            rsi24=f"{self._current_detail.get('rsi24', 0.0):.1f}",
            boll_up=f"{self._current_detail.get('boll_up', 0.0):.2f}",
            boll_mid=f"{self._current_detail.get('boll_mid', 0.0):.2f}",
            boll_low=f"{self._current_detail.get('boll_low', 0.0):.2f}",
            roe=self._current_detail.get("roe", 15.0),
            revenue_growth=self._current_detail.get("revenue_growth", 10.0),
            profit_growth=self._current_detail.get("profit_growth", 12.0),
            debt_ratio=self._current_detail.get("debt_ratio", 40.0),
            news_summary=news_summary or "近期无重大舆情风险事件，基本面经营平稳。"
        )

        # 启动异步工作线程
        self._worker = AIStreamWorker(STOCK_ANALYSIS_SYSTEM_PROMPT, user_prompt)
        self._worker.chunk_received.connect(self._on_chunk_received)
        self._worker.finished_signal.connect(self._on_report_finished)
        self._worker.start()

    def _on_chunk_received(self, chunk: str):
        """流式追加文本并自动滚动到底部"""
        cursor = self.txt_report.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(chunk)
        self.txt_report.setTextCursor(cursor)

    def _on_report_finished(self, full_report: str):
        """报告生成完毕"""
        self.btn_ai_report.setEnabled(True)
        self.btn_ai_report.setText("AI 一键深度研报")
        
        # 保存至 SQLite
        session = db_manager.get_session()
        try:
            rep = AnalysisReport(
                symbol=self.current_symbol,
                model_name=llm_client._current_provider_name,
                overall_score=85.0,
                signal="看多",
                report_markdown=full_report
            )
            session.add(rep)
            session.commit()
            logger.info("个股 [%s] AI 诊断报告已成功持久化落盘。", self.current_symbol)
        except Exception as e:
            session.rollback()
            logger.error("保存研报入库异常: %s", str(e))
        finally:
            session.close()

    def _on_fav_toggle(self):
        """切换自选状态"""
        if watchlist_service.is_in_watchlist(self.current_symbol):
            watchlist_service.remove_from_watchlist(self.current_symbol)
            self.btn_fav.setText("加入自选")
        else:
            watchlist_service.add_to_watchlist(self.current_symbol)
            self.btn_fav.setText("已在自选")

    def _on_search_stock(self):
        """手动搜索代码并切换当前标的"""
        sym = self.input_search.text().strip()
        if sym:
            sym = sym.zfill(6)
            self.load_stock(sym)
            self.input_search.clear()

    def _on_virtual_buy(self):
        """弹出模拟买入建仓对话框"""
        dlg = BuyDialog(self, default_symbol=self.current_symbol)
        dlg.exec()
