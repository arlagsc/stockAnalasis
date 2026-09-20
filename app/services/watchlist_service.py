# -*- coding: utf-8 -*-
"""自选股池与监控管理服务

提供自选股票的添加、移除、分组归类、便签备注维护
以及与实时行情的联动查询。
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
from sqlalchemy import select, delete

from app.core.config import logger
from app.core.database import db_manager, Watchlist, StockBasic
from app.services.data_service import data_service

class WatchlistService:
    """自选股业务服务管理器"""

    def add_to_watchlist(self, symbol: str, group_name: str = "默认自选", notes: str = "") -> bool:
        """将指定股票加入自选池"""
        symbol = str(symbol).zfill(6)
        session = db_manager.get_session()
        try:
            existing = session.query(Watchlist).filter(Watchlist.symbol == symbol).first()
            if existing:
                existing.group_name = group_name
                if notes:
                    existing.notes = notes
            else:
                item = Watchlist(symbol=symbol, group_name=group_name, notes=notes)
                session.add(item)
            session.commit()
            logger.info("已将股票 [%s] 成功加入自选池 (分组: %s)", symbol, group_name)
            return True
        except Exception as e:
            session.rollback()
            logger.error("添加自选股异常: %s", str(e))
            return False
        finally:
            session.close()

    def remove_from_watchlist(self, symbol: str) -> bool:
        """从自选池中移除指定股票"""
        symbol = str(symbol).zfill(6)
        session = db_manager.get_session()
        try:
            session.query(Watchlist).filter(Watchlist.symbol == symbol).delete()
            session.commit()
            logger.info("已将股票 [%s] 从自选池中移除", symbol)
            return True
        except Exception as e:
            session.rollback()
            logger.error("移除自选股异常: %s", str(e))
            return False
        finally:
            session.close()

    def is_in_watchlist(self, symbol: str) -> bool:
        """查询某股票是否已被收录在自选池"""
        symbol = str(symbol).zfill(6)
        session = db_manager.get_session()
        try:
            item = session.query(Watchlist).filter(Watchlist.symbol == symbol).first()
            return item is not None
        finally:
            session.close()

    def get_watchlist_with_quotes(self, group_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取自选股清单并合并最新量化行情与估值数据"""
        session = db_manager.get_session()
        try:
            query = session.query(Watchlist)
            if group_filter and group_filter != "全部分组":
                query = query.filter(Watchlist.group_name == group_filter)
            watchlist_items = query.all()
            if not watchlist_items:
                return []

            symbols = [item.symbol for item in watchlist_items]
            meta_map = {item.symbol: {"group": item.group_name, "notes": item.notes} for item in watchlist_items}
        finally:
            session.close()

        # 合并全景行情数据
        universe = data_service.get_stock_universe()
        results = []
        if not universe.empty and "symbol" in universe.columns:
            matched = universe[universe["symbol"].isin(symbols)]
            for _, row in matched.iterrows():
                sym = row["symbol"]
                d = row.to_dict()
                d["group_name"] = meta_map.get(sym, {}).get("group", "默认自选")
                d["notes"] = meta_map.get(sym, {}).get("notes", "")
                results.append(d)
        return results

    def get_all_groups(self) -> List[str]:
        """获取当前存在的所有自选分组列表"""
        session = db_manager.get_session()
        try:
            groups = session.query(Watchlist.group_name).distinct().all()
            return [g[0] for g in groups if g[0]] or ["默认自选"]
        finally:
            session.close()

    def get_watchlist_simple(self) -> List[Dict[str, str]]:
        """获取极简自选股列表用于下拉选择快速切换 (仅含代码与名称，毫秒级)"""
        session = db_manager.get_session()
        try:
            results = (
                session.query(Watchlist.symbol, StockBasic.name)
                .outerjoin(StockBasic, Watchlist.symbol == StockBasic.symbol)
                .order_by(Watchlist.id.asc())
                .all()
            )
            items = []
            for sym, name in results:
                items.append({
                    "symbol": sym,
                    "name": name or f"标的{sym}",
                })
            return items
        except Exception as e:
            logger.error("查询极简自选股列表异常: %s", str(e))
            return []
        finally:
            session.close()

# 单例
watchlist_service = WatchlistService()
