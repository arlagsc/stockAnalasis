# -*- coding: utf-8 -*-
"""数据缓存与本地同步管理器

管理 A 股基础行情数据在本地 SQLite 数据库中的落盘、
增量更新、缓存时效判断以及内存矩阵快速索引。
"""

import threading
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
        self._is_syncing: bool = False
        self._sync_lock = threading.Lock()

    def get_stocks_dataframe(self, force_refresh: bool = False) -> pd.DataFrame:
        """获取全市场股票最新数据 DataFrame

        若内存缓存有效则直接返回；否则从 SQLite 读取；
        若本地数据库为空或已过期，则触发同步抓取。
        """
        now = datetime.now()
        is_trading_hour = (9 <= now.hour <= 15) and (now.weekday() < 5)
        ttl = 60 if is_trading_hour else 1800

        if not force_refresh and self._cached_df is not None and not self._cached_df.empty:
            if self._last_loaded_time and (now - self._last_loaded_time).total_seconds() < ttl:
                return self._cached_df

        # 尝试从本地 SQLite 读取
        session = db_manager.get_session()
        try:
            stocks = session.query(StockBasic).all()
            if stocks and not force_refresh:
                # 检查数据是否陈旧
                latest_update = max((s.updated_at for s in stocks if s.updated_at), default=datetime.min)
                is_stale = False
                if is_trading_hour:
                    today_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
                    if latest_update < today_start or (now - latest_update).total_seconds() > 300:
                        is_stale = True
                elif (now - latest_update).total_seconds() > 86400:
                    is_stale = True

                data = [s.to_dict() for s in stocks]
                df = pd.DataFrame(data)
                self._cached_df = df
                self._last_loaded_time = now

                # 如果数据已过期且未在同步中，异步启动后台静默更新，不阻塞当前请求
                if is_stale and not self._is_syncing:
                    logger.info("本地 SQLite 行情数据已过期 (最新时间: %s)，启动后台静默同步...", latest_update)
                    threading.Thread(target=self.sync_stocks_from_source, daemon=True).start()

                return df
        except Exception as e:
            logger.error("从本地 SQLite 读取股票数据异常: %s", str(e))
        finally:
            session.close()

        # 本地完全无数据或强制刷新，执行全量同步
        return self.sync_stocks_from_source()

    def sync_stocks_from_source(self) -> pd.DataFrame:
        """从外部源拉取全景行情并更新写入本地 SQLite"""
        with self._sync_lock:
            if self._is_syncing:
                return self._cached_df if self._cached_df is not None else pd.DataFrame()
            self._is_syncing = True

        try:
            logger.info("开始执行外部全量行情数据抓取与本地持久化同步...")
            df = data_fetcher.fetch_all_stock_basics()
            if df.empty:
                logger.warning("抓取返回空数据，取消本地落盘。")
                return self._cached_df if self._cached_df is not None else pd.DataFrame()

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
        finally:
            self._is_syncing = False

# 全局缓存管理器单例
cache_manager = CacheManager()
