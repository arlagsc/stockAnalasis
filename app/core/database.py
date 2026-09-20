# -*- coding: utf-8 -*-
"""数据库与本地持久化模块

基于 SQLite 与 SQLAlchemy 实现股票基础代码表、自选股池、
AI 诊断研报与智能筛选策略的本地持久化与事务管理。
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text, DateTime, Boolean, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from app.core.config import config, logger

Base = declarative_base()

class StockBasic(Base):
    """A 股股票基础信息与简要行情表"""
    __tablename__ = "stock_basic"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(16), unique=True, nullable=False, index=True, comment="股票代码，如 600519")
    name = Column(String(64), nullable=False, index=True, comment="股票简称，如 贵州茅台")
    industry = Column(String(64), default="未知", index=True, comment="所属细分行业")
    market = Column(String(16), default="主板", comment="板块：主板/创业板/科创板/北交所")
    
    # 最新基础量价与估值指标
    close_price = Column(Float, default=0.0, comment="最新收盘价")
    change_pct = Column(Float, default=0.0, comment="最新涨跌幅(%)")
    volume = Column(Float, default=0.0, comment="成交量(手)")
    turnover_rate = Column(Float, default=0.0, comment="换手率(%)")
    pe_ratio = Column(Float, default=0.0, comment="市盈率(TTM)")
    pb_ratio = Column(Float, default=0.0, comment="市净率")
    total_market_val = Column(Float, default=0.0, comment="总市值(亿元)")
    
    # 常用技术指标快照
    ma5 = Column(Float, default=0.0, comment="5日均线")
    ma20 = Column(Float, default=0.0, comment="20日均线")
    rsi6 = Column(Float, default=0.0, comment="RSI(6)")
    macd = Column(Float, default=0.0, comment="MACD差离值")

    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间戳")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "industry": self.industry,
            "market": self.market,
            "close_price": self.close_price,
            "change_pct": self.change_pct,
            "volume": self.volume,
            "turnover_rate": self.turnover_rate,
            "pe_ratio": self.pe_ratio,
            "pb_ratio": self.pb_ratio,
            "total_market_val": self.total_market_val,
            "ma5": self.ma5,
            "ma20": self.ma20,
            "rsi6": self.rsi6,
            "macd": self.macd,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else "",
        }

class Watchlist(Base):
    """自选股池管理表"""
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(16), unique=True, nullable=False, index=True, comment="股票代码")
    group_name = Column(String(64), default="默认自选", comment="分组名称")
    notes = Column(Text, default="", comment="投资笔记或自定义标签")
    alert_high = Column(Float, nullable=True, comment="上限止盈提醒价")
    alert_low = Column(Float, nullable=True, comment="下限止损提醒价")
    created_at = Column(DateTime, default=datetime.now, comment="加入自选时间")

class AnalysisReport(Base):
    """个股 AI 深度研报记录表"""
    __tablename__ = "analysis_report"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(16), nullable=False, index=True, comment="股票代码")
    model_name = Column(String(64), nullable=False, comment="分析使用的大模型名称")
    overall_score = Column(Float, default=0.0, comment="模型综合打分(0-100)")
    signal = Column(String(16), default="中性", comment="评级方向：看多/中性/看空")
    report_markdown = Column(Text, nullable=False, comment="报告全文 Markdown")
    created_at = Column(DateTime, default=datetime.now, comment="生成时间")

class ScreenerStrategy(Base):
    """用户自定义筛选策略持久化表"""
    __tablename__ = "screener_strategy"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(128), nullable=False, comment="策略名称")
    rules_json = Column(Text, nullable=False, comment="过滤规则集合序列化")
    nl_prompt = Column(Text, default="", comment="原始自然语言提示词")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

class DatabaseManager:
    """本地数据库会话管理器"""

    def __init__(self):
        db_uri = f"sqlite:///{config.db_path}"
        self.engine = create_engine(
            db_uri,
            echo=False,
            connect_args={"check_same_thread": False},  # 支持多线程并发读写
        )
        self.session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(self.session_factory)
        self._init_db()

    def _init_db(self):
        """自动建表与升级结构"""
        try:
            Base.metadata.create_all(self.engine)
            logger.info("SQLite 数据库初始化与表结构校验完成。路径: %s", config.db_path)
        except Exception as e:
            logger.error("数据库初始化异常: %s", str(e))

    def get_session(self):
        """获取独立数据库会话上下文"""
        return self.Session()

# 全局数据库管理器导出
db_manager = DatabaseManager()
