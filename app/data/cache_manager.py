# -*- coding: utf-8 -*-
"""数据缓存与本地同步管理器

管理 A 股基础行情数据在本地 SQLite 数据库中的落盘、
增量更新、缓存时效判断以及内存矩阵快速索引。
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd
from sqlalchemy import select, delete

from app.core.config import config, logger
from app.core.database import db_manager, StockBasic
from app.data.fetcher import data_fetcher
from app.data.indicators import indicator_engine

class CacheManager:
    """本地数据缓存与生命周期管理器"""

    def __init__(self):
        self._cached_df: Optional[pd.DataFrame] = None
        self._last_loaded_time: Optional[datetime] = None

    def get_stocks_dataframe(self, force_refresh: bool = False) -> pd.DataFrame:
        """获取全市场股票最新数据 DataFrame
        
        若内存缓存有效则直接返回；否则从 SQLite 读取；
        若本地数据库为空或已过期，则触发同步抓取。
        """
        now = datetime.now()
        if not force_refresh and self._cached_df is not None and not self._cached_df.empty:
            if self._last_loaded_time and (now - self._last_loaded_time).total_seconds() < 1800:
                return self._cached_df

        # 尝试从本地 SQLite 读取
        session = db_manager.get_session()
        try:
            stocks = session.query(StockBasic).all()
            if stocks and not force_refresh:
                data = [s.to_dict() for s in stocks]
                df = pd.DataFrame(data)
                self._cached_df = df
                self._last_loaded_time = now
                logger.info("从本地 SQLite 成功装载 %d 只股票数据至内存。", len(df))
                return df
        except Exception as e:
            logger.error("从本地 SQLite 读取股票数据异常: %s", str(e))
        finally:
            session.close()

        # 本地无数据或强制刷新，执行全量同步
        return self.sync_stocks_from_source()

    def sync_stocks_from_source(self) -> pd.DataFrame:
        """从外部源拉取全景行情并更新写入本地 SQLite"""
        logger.info("开始执行外部行情数据抓取与本地持久化同步...")
        df = data_fetcher.fetch_all_stock_basics()
        if df.empty:
            logger.warning("抓取返回空数据，取消本地落盘。")
            return pd.DataFrame()

        session = db_manager.get_session()
        try:
            # 清空旧基础数据
            session.query(StockBasic).delete()
            
            # 批量组装实体并插入
            records = []
            now = datetime.now()
            for _, row in df.iterrows():
                sb = StockBasic(
                    symbol=str(row.get("symbol", "")).zfill(6),
                    name=str(row.get("name", "")),
                    industry=str(row.get("industry", "常规板块")),
                    close_price=float(row.get("close_price", 0.0)),
                    change_pct=float(row.get("change_pct", 0.0)),
                    volume=float(row.get("volume", 0.0)),
                    turnover_rate=float(row.get("turnover_rate", 0.0)),
                    pe_ratio=float(row.get("pe_ratio", 0.0)),
                    pb_ratio=float(row.get("pb_ratio", 0.0)),
                    total_market_val=float(row.get("total_market_val", 0.0)),
                    updated_at=now,
                )
                records.append(sb)

            session.bulk_save_objects(records)
            session.commit()
            logger.info("已成功批量同步 %d 条股票记录入库 SQLite。", len(records))

            self._cached_df = df
            self._last_loaded_time = now
            return df
        except Exception as e:
            session.rollback()
            logger.error("批量同步股票数据入库异常: %s", str(e))
            return df
        finally:
            session.close()

# 全局缓存管理器单例
cache_manager = CacheManager()
