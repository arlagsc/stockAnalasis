# -*- coding: utf-8 -*-
"""股票行情与多维分析业务服务

为 UI 表现层提供统一的高性能数据接口，
包含全景股票行情查询、单股 K 线时序与全套技术指标计算集成。
"""

from typing import List, Dict, Any, Optional
import pandas as pd

from app.core.config import logger
from app.data.cache_manager import cache_manager
from app.data.fetcher import data_fetcher
from app.data.indicators import indicator_engine

class DataService:
    """股票数据业务聚合服务"""

    def get_stock_universe(self, force_refresh: bool = False) -> pd.DataFrame:
        """获取全市场股票池基础 DataFrame"""
        return cache_manager.get_stocks_dataframe(force_refresh=force_refresh)

    def get_stock_detail(self, symbol: str) -> Dict[str, Any]:
        """获取指定股票的多维详情（包含基本面快照、技术指标快照与财务摘要）"""
        symbol = str(symbol).zfill(6)
        universe = self.get_stock_universe()
        
        stock_info = {}
        if not universe.empty and "symbol" in universe.columns:
            matched = universe[universe["symbol"] == symbol]
            if not matched.empty:
                stock_info = matched.iloc[0].to_dict()

        # 获取日 K 线与技术指标
        kline_df = data_fetcher.fetch_stock_daily_kline(symbol, count=120)
        kline_with_indicators = indicator_engine.calculate_all_indicators(kline_df)
        snapshot = indicator_engine.extract_latest_snapshot(kline_with_indicators)
        
        # 获取财务指标与新闻
        fin_summary = data_fetcher.fetch_financial_summary(symbol)
        news = data_fetcher.fetch_stock_news(symbol, limit=3)

        # 合并结果字典
        combined = {**stock_info, **snapshot, **fin_summary}
        combined["news_list"] = news
        combined["kline_df"] = kline_with_indicators
        return combined

    def get_stock_kline_with_indicators(self, symbol: str, count: int = 150) -> pd.DataFrame:
        """获取用于 PyQtGraph 渲染的完整带指标 K 线 DataFrame"""
        raw_kline = data_fetcher.fetch_stock_daily_kline(symbol, count=count)
        return indicator_engine.calculate_all_indicators(raw_kline)

# 全局数据服务单例
data_service = DataService()
