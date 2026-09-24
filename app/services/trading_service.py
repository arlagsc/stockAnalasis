# -*- coding: utf-8 -*-
"""虚拟建仓与实盘级仿真交易撮合引擎

提供人手操盘与 AI 智能操盘独立双账户体系，支持：
1. 用户自定义初始资金与随时一键重置账户；
2. A 股真实盘口撮合与 T+1 交易纪律约束（当日买入次日可卖）；
3. 真实交易摩擦成本（印花税 0.05%、券商佣金万分之二，最低 5 元）；
4. 实时市值动态跟踪、持仓浮动盈亏计算与成交流水归档。
"""

from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
from sqlalchemy import desc

from app.core.config import logger
from app.core.database import (
    db_manager, VirtualAccount, VirtualPosition, VirtualTrade
)
from app.data.fetcher import data_fetcher

class TradingService:
    """虚拟仿真交易撮合与账户核算服务单例"""

    def __init__(self):
        self._ensure_default_accounts()

    def _ensure_default_accounts(self, default_capital: float = 1000000.0):
        """确保 MANUAL 与 AI 双账户在数据库中初始化完毕"""
        session = db_manager.get_session()
        try:
            for acc_type in ["MANUAL", "AI"]:
                acc = session.query(VirtualAccount).filter_by(account_type=acc_type).first()
                if not acc:
                    acc = VirtualAccount(
                        account_type=acc_type,
                        initial_capital=default_capital,
                        available_cash=default_capital
                    )
                    session.add(acc)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error("初始化虚拟交易账户异常: %s", str(e))
        finally:
            session.close()

    def reset_account(self, account_type: str, initial_capital: float) -> bool:
        """重置指定账户（清空持仓与流水，重新设定初始可用现金）"""
        session = db_manager.get_session()
        try:
            acc = session.query(VirtualAccount).filter_by(account_type=account_type).first()
            if not acc:
                acc = VirtualAccount(account_type=account_type)
                session.add(acc)
            
            acc.initial_capital = float(initial_capital)
            acc.available_cash = float(initial_capital)
            acc.updated_at = datetime.now()

            # 清理该账户的历史持仓与成交
            session.query(VirtualPosition).filter_by(account_type=account_type).delete()
            session.query(VirtualTrade).filter_by(account_type=account_type).delete()
            session.commit()
            logger.info("账户 [%s] 已成功重置，初始资金: %.2f 元", account_type, initial_capital)
            return True
        except Exception as e:
            session.rollback()
            logger.error("重置账户异常: %s", str(e))
            return False
        finally:
            session.close()

    def buy_stock(
        self,
        account_type: str,
        symbol: str,
        amount: int,
        custom_price: Optional[float] = None,
        name: Optional[str] = None,
        reason: str = "手动择时买入"
    ) -> Tuple[bool, str]:
        """执行仿真建仓买入操作
        
        撮合规则:
        - 买入必须是 100 股的整数倍 (最少 100 股/1手);
        - 扣除佣金万分之二 (最低 5 元);
        - 当日买入标记为 T+1 锁定，当日 available_amount 不增加。
        """
        symbol = str(symbol).zfill(6)
        if amount <= 0 or amount % 100 != 0:
            return False, "买入股数必须为 100 的整数倍 (至少 1 手 100 股)"

        # 获取标的盘口现价与名称
        stock_name = (name or "").strip()
        if not stock_name or stock_name.startswith("标的"):
            stock_name = "标的" + symbol

        price = custom_price
        need_quote = (price is None or price <= 0 or stock_name.startswith("标的"))

        if need_quote:
            q_map = data_fetcher.fetch_specific_quotes([symbol])
            if symbol in q_map:
                if price is None or price <= 0:
                    price = float(q_map[symbol].get("close_price", 0.0))
                fetched_name = str(q_map[symbol].get("name", "")).strip()
                if fetched_name:
                    stock_name = fetched_name
            
            if stock_name.startswith("标的") or price is None or price <= 0:
                # 离线或备选本地数据库查询
                df = data_fetcher.fetch_all_stock_basics()
                if not df.empty and "symbol" in df.columns:
                    matched = df[df["symbol"] == symbol]
                    if not matched.empty:
                        row = matched.iloc[0]
                        if price is None or price <= 0:
                            price = float(row.get("close_price", 0.0))
                        fetched_name = str(row.get("name", "")).strip()
                        if fetched_name:
                            stock_name = fetched_name

        if price is None or price <= 0:
            price = 10.0  # 离线极值兜底

        # 计算费用
        trade_value = round(price * amount, 2)
        commission = max(5.0, round(trade_value * 0.0002, 2))  # 万分之二，最低 5 元
        total_cost = trade_value + commission

        today_str = date.today().strftime("%Y-%m-%d")
        session = db_manager.get_session()
        try:
            acc = session.query(VirtualAccount).filter_by(account_type=account_type).first()
            if not acc or acc.available_cash < total_cost:
                return False, f"账户可用资金不足！需 {total_cost:.2f} 元，当前可用 {acc.available_cash if acc else 0:.2f} 元"

            # 扣除现金
            acc.available_cash = round(acc.available_cash - total_cost, 2)
            acc.updated_at = datetime.now()

            # 更新持仓
            pos = session.query(VirtualPosition).filter_by(account_type=account_type, symbol=symbol).first()
            if not pos:
                pos = VirtualPosition(
                    account_type=account_type,
                    symbol=symbol,
                    name=stock_name,
                    total_amount=amount,
                    available_amount=0,  # T+1: 当天买入不可卖
                    cost_price=price,
                    current_price=price,
                    last_buy_date=today_str,
                )
                session.add(pos)
            else:
                # 摊薄持仓均价
                new_total = pos.total_amount + amount
                new_cost = round(((pos.cost_price * pos.total_amount) + trade_value) / new_total, 3)
                pos.total_amount = new_total
                pos.cost_price = new_cost
                pos.current_price = price
                pos.last_buy_date = today_str

            # 写入成交流水表
            trade = VirtualTrade(
                account_type=account_type,
                symbol=symbol,
                name=stock_name,
                action="BUY",
                price=price,
                amount=amount,
                total_value=trade_value,
                tax_fee=0.0,
                commission_fee=commission,
                realized_pnl=0.0,
                realized_pct=0.0,
                reason=reason or "逢低建仓",
                trade_time=datetime.now(),
            )
            session.add(trade)
            session.commit()
            logger.info("账户 [%s] 成功买入 [%s %s] %d 股，均价: %.2f 元", account_type, symbol, stock_name, amount, price)
            return True, f"成功买入 {stock_name}({symbol}) {amount} 股，成交均价: {price:.2f} 元"
        except Exception as e:
            session.rollback()
            logger.error("买入撮合异常: %s", str(e))
            return False, f"买入撮合异常: {str(e)}"
        finally:
            session.close()

    def sell_stock(
        self,
        account_type: str,
        symbol: str,
        amount: int,
        custom_price: Optional[float] = None,
        reason: str = "获利了结或止损出局"
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """执行仿真平仓卖出操作
        
        撮合规则:
        - 必须遵守 T+1 交易纪律 (可卖股数 available_amount >= amount);
        - 扣除佣金万分之二 (最低 5 元) 与印花税 0.05%;
        - 结清收益后现金实时返还可用余额;
        - 返回该笔交易的完整生命周期明细，用于 AI 归因反思。
        """
        symbol = str(symbol).zfill(6)
        if amount <= 0:
            return False, "卖出股数必须大于 0", None

        session = db_manager.get_session()
        try:
            # 自动维护 T+1 状态
            self._update_t1_available_within_session(session, account_type)

            pos = session.query(VirtualPosition).filter_by(account_type=account_type, symbol=symbol).first()
            if not pos:
                return False, f"未持有标的 [{symbol}]，无法卖出", None
            if pos.available_amount < amount:
                return False, f"今日可卖数量不足！总持股 {pos.total_amount} 股，今日可卖 {pos.available_amount} 股 (受 T+1 规则限制)", None

            price = custom_price
            if price is None or price <= 0:
                price = pos.current_price if pos.current_price > 0 else pos.cost_price

            gross_value = round(price * amount, 2)
            commission = max(5.0, round(gross_value * 0.0002, 2))
            tax = round(gross_value * 0.0005, 2)  # 印花税 0.05%
            net_proceeds = gross_value - commission - tax

            # 计算此笔卖出的实现盈亏
            cost_value = round(pos.cost_price * amount, 2)
            realized_pnl = round(net_proceeds - cost_value, 2)
            realized_pct = round((realized_pnl / cost_value) * 100, 2) if cost_value > 0 else 0.0

            # 资金回流账户
            acc = session.query(VirtualAccount).filter_by(account_type=account_type).first()
            if acc:
                acc.available_cash = round(acc.available_cash + net_proceeds, 2)
                acc.updated_at = datetime.now()

            # 更新或清空持仓
            pos.total_amount -= amount
            pos.available_amount -= amount
            if pos.total_amount <= 0:
                session.delete(pos)
            else:
                pos.updated_at = datetime.now()

            # 写入成交流水表
            trade = VirtualTrade(
                account_type=account_type,
                symbol=symbol,
                name=pos.name,
                action="SELL",
                price=price,
                amount=amount,
                total_value=gross_value,
                tax_fee=tax,
                commission_fee=commission,
                realized_pnl=realized_pnl,
                realized_pct=realized_pct,
                reason=reason,
                trade_time=datetime.now(),
            )
            session.add(trade)
            session.commit()
            logger.info("账户 [%s] 成功卖出 [%s %s] %d 股，实现盈亏: %.2f 元 (%.2f%%)", account_type, symbol, pos.name, amount, realized_pnl, realized_pct)

            # 组装复盘交易包
            trade_summary = {
                "account_type": account_type,
                "symbol": symbol,
                "name": pos.name,
                "action": "SELL",
                "sell_price": price,
                "cost_price": pos.cost_price,
                "amount": amount,
                "realized_pnl": realized_pnl,
                "realized_pct": realized_pct,
                "trade_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "reason": reason,
            }
            return True, f"成功平仓 {pos.name}({symbol}) {amount} 股，实现盈亏: {realized_pnl:+.2f} 元 ({realized_pct:+.2f}%)", trade_summary
        except Exception as e:
            session.rollback()
            logger.error("卖出撮合异常: %s", str(e))
            return False, f"卖出撮合异常: {str(e)}", None
        finally:
            session.close()

    def _update_t1_available_within_session(self, session, account_type: str):
        """若跨越交易日，自动解冻 T+1 可卖股数"""
        today_str = date.today().strftime("%Y-%m-%d")
        positions = session.query(VirtualPosition).filter_by(account_type=account_type).all()
        for p in positions:
            if p.last_buy_date and p.last_buy_date != today_str:
                p.available_amount = p.total_amount

    def refresh_positions_quotes(self, account_type: Optional[str] = None):
        """通过定向高速通道批量刷新持仓标的的最新盘口价格与估值（毫秒级，杜绝全市场 5565 支遍历）"""
        session = db_manager.get_session()
        try:
            query = session.query(VirtualPosition)
            if account_type:
                query = query.filter_by(account_type=account_type)
            positions = query.all()
            if not positions:
                return

            symbols = list(set([p.symbol for p in positions if p.symbol]))
            if not symbols:
                return

            # 定向批量获取持仓标的盘口价格
            quote_map = data_fetcher.fetch_specific_quotes(symbols)

            today_str = date.today().strftime("%Y-%m-%d")
            for p in positions:
                if p.symbol in quote_map:
                    latest_p = quote_map[p.symbol].get("close_price", 0.0)
                    if latest_p > 0:
                        p.current_price = latest_p
                    real_name = str(quote_map[p.symbol].get("name", "")).strip()
                    if real_name and (not p.name or p.name.startswith("标的")):
                        p.name = real_name
                # T+1 解冻校验
                if p.last_buy_date and p.last_buy_date != today_str:
                    p.available_amount = p.total_amount

            session.commit()
            logger.info("已成功批量定向刷新持仓最新价格，覆盖标的数: %d", len(symbols))
        except Exception as e:
            session.rollback()
            logger.error("刷新持仓盘口异常: %s", str(e))
        finally:
            session.close()

    def get_account_summary(self, account_type: str) -> Dict[str, Any]:
        """获取账户总览资产统计与表现指标"""
        session = db_manager.get_session()
        try:
            acc = session.query(VirtualAccount).filter_by(account_type=account_type).first()
            if not acc:
                return {
                    "account_type": account_type,
                    "initial_capital": 1000000.0,
                    "available_cash": 1000000.0,
                    "market_value": 0.0,
                    "total_equity": 1000000.0,
                    "total_return_pct": 0.0,
                    "floating_pnl": 0.0,
                    "position_count": 0,
                }

            positions = session.query(VirtualPosition).filter_by(account_type=account_type).all()
            total_mkt_val = 0.0
            total_floating_pnl = 0.0
            for p in positions:
                cur_p = p.current_price if p.current_price > 0 else p.cost_price
                mkt = round(cur_p * p.total_amount, 2)
                pnl = round((cur_p - p.cost_price) * p.total_amount, 2)
                total_mkt_val += mkt
                total_floating_pnl += pnl

            total_equity = round(acc.available_cash + total_mkt_val, 2)
            init_cap = acc.initial_capital if acc.initial_capital > 0 else 1000000.0
            total_return_pct = round(((total_equity - init_cap) / init_cap) * 100, 2)

            return {
                "account_type": account_type,
                "initial_capital": init_cap,
                "available_cash": acc.available_cash,
                "market_value": round(total_mkt_val, 2),
                "total_equity": total_equity,
                "total_return_pct": total_return_pct,
                "floating_pnl": round(total_floating_pnl, 2),
                "position_count": len(positions),
            }
        finally:
            session.close()

    def get_positions(self, account_type: str) -> List[Dict[str, Any]]:
        """获取指定账户的当前持仓列表"""
        session = db_manager.get_session()
        try:
            positions = session.query(VirtualPosition).filter_by(account_type=account_type).all()
            res = []
            for p in positions:
                cur_p = p.current_price if p.current_price > 0 else p.cost_price
                mkt = round(cur_p * p.total_amount, 2)
                pnl = round((cur_p - p.cost_price) * p.total_amount, 2)
                pnl_pct = round(((cur_p - p.cost_price) / p.cost_price) * 100, 2) if p.cost_price > 0 else 0.0
                res.append({
                    "symbol": p.symbol,
                    "name": p.name,
                    "total_amount": p.total_amount,
                    "available_amount": p.available_amount,
                    "cost_price": p.cost_price,
                    "current_price": cur_p,
                    "market_value": mkt,
                    "floating_pnl": pnl,
                    "floating_pnl_pct": pnl_pct,
                })
            return res
        finally:
            session.close()

    def get_trades_history(self, account_type: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """获取最近成交流水记录"""
        session = db_manager.get_session()
        try:
            query = session.query(VirtualTrade)
            if account_type:
                query = query.filter_by(account_type=account_type)
            trades = query.order_by(desc(VirtualTrade.trade_time)).limit(limit).all()
            res = []
            for t in trades:
                res.append({
                    "id": t.id,
                    "account_type": t.account_type,
                    "symbol": t.symbol,
                    "name": t.name,
                    "action": t.action,
                    "price": t.price,
                    "amount": t.amount,
                    "total_value": t.total_value,
                    "tax_fee": t.tax_fee,
                    "commission_fee": t.commission_fee,
                    "realized_pnl": t.realized_pnl,
                    "realized_pct": t.realized_pct,
                    "reason": t.reason,
                    "trade_time": t.trade_time.strftime("%Y-%m-%d %H:%M:%S") if t.trade_time else "",
                })
            return res
        finally:
            session.close()

# 全局仿真交易服务单例
trading_service = TradingService()
