# -*- coding: utf-8 -*-
"""金融量化技术指标计算引擎

基于 Pandas 与 NumPy 实现高效的向量化计算。
支持针对单个股票历史时序计算技术指标，
以及针对全市场快照矩阵快速计算筛选因子。
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
from app.core.config import logger

class IndicatorEngine:
    """金融技术指标向量化计算引擎"""

    @staticmethod
    def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """为股票历史日 K 线数据计算全套核心技术指标
        
        要求 df 必须包含以下字段（大小写不敏感）：
        date, open, high, low, close, volume
        
        返回扩充后的 DataFrame
        """
        if df.empty or len(df) < 5:
            logger.warning("输入数据量不足 (len < 5)，无法计算完整技术指标。")
            return df

        df = df.copy()
        # 标准化列名为小写
        df.columns = [str(col).lower() for col in df.columns]

        # 确保数值类型正确
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").ffill()

        # 1. 均线系统 (Moving Averages)
        df["ma5"] = df["close"].rolling(window=5, min_periods=1).mean()
        df["ma10"] = df["close"].rolling(window=10, min_periods=1).mean()
        df["ma20"] = df["close"].rolling(window=20, min_periods=1).mean()
        df["ma60"] = df["close"].rolling(window=60, min_periods=1).mean()

        # 2. 指数平滑异同移动平均线 (MACD)
        # 短期 12，长期 26，信号线 9
        exp12 = df["close"].ewm(span=12, adjust=False).mean()
        exp26 = df["close"].ewm(span=26, adjust=False).mean()
        df["dif"] = exp12 - exp26
        df["dea"] = df["dif"].ewm(span=9, adjust=False).mean()
        df["macd"] = 2 * (df["dif"] - df["dea"])

        # 3. 相对强弱指标 (RSI 6, 12, 24)
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).fillna(0)
        loss = (-delta.where(delta < 0, 0)).fillna(0)

        for period in [6, 12, 24]:
            avg_gain = gain.rolling(window=period, min_periods=1).mean()
            avg_loss = loss.rolling(window=period, min_periods=1).mean()
            rs = avg_gain / (avg_loss + 1e-9)
            df[f"rsi{period}"] = 100 - (100 / (1 + rs))

        # 4. 布林带 (BOLL: 20, 2)
        df["boll_mid"] = df["close"].rolling(window=20, min_periods=1).mean()
        std20 = df["close"].rolling(window=20, min_periods=1).std(ddof=0).fillna(0)
        df["boll_up"] = df["boll_mid"] + 2 * std20
        df["boll_low"] = df["boll_mid"] - 2 * std20

        # 5. 随机指标 (KDJ: 9, 3, 3)
        low_min = df["low"].rolling(window=9, min_periods=1).min()
        high_max = df["high"].rolling(window=9, min_periods=1).max()
        rsv = ((df["close"] - low_min) / (high_max - low_min + 1e-9)) * 100
        df["kdj_k"] = rsv.ewm(com=2, adjust=False).mean()
        df["kdj_d"] = df["kdj_k"].ewm(com=2, adjust=False).mean()
        df["kdj_j"] = 3 * df["kdj_k"] - 2 * df["kdj_d"]

        # 6. 成交量均线
        df["vol_ma5"] = df["volume"].rolling(window=5, min_periods=1).mean()
        df["vol_ma10"] = df["volume"].rolling(window=10, min_periods=1).mean()

        logger.debug("已完成 %d 条 K 线的全套技术指标计算", len(df))
        return df

    @staticmethod
    def extract_latest_snapshot(df: pd.DataFrame) -> Dict[str, float]:
        """提取最新一根 K 线的各技术指标快照"""
        if df.empty:
            return {}
        last_row = df.iloc[-1]
        keys = [
            "close", "open", "high", "low", "volume",
            "ma5", "ma10", "ma20", "ma60",
            "dif", "dea", "macd",
            "rsi6", "rsi12", "rsi24",
            "boll_mid", "boll_up", "boll_low",
            "kdj_k", "kdj_d", "kdj_j"
        ]
        return {k: float(last_row.get(k, 0.0)) for k in keys if k in last_row}

# 导出单例引擎
indicator_engine = IndicatorEngine()
