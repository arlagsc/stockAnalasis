# -*- coding: utf-8 -*-
"""StockAI 移动端轻量 RESTful API 与静态服务

为 iPhone PWA 提供异步高性能数据接口，涵盖大盘概览、自选股池、
智能推荐卡片流、个股技术图表与双轨虚拟操盘交易接口。
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pypinyin import pinyin, Style

from app.core.config import logger, APP_VERSION, APP_NAME
from app.services.data_service import data_service
from app.services.watchlist_service import watchlist_service
from app.services.trading_service import trading_service
from app.services.recommend_service import recommend_service
from app.services.auto_trader import auto_trader
from app.ai.skill_engine import skill_engine
from app.data.fetcher import data_fetcher

# 0. 拼音首字母提取与索引单例缓存
def get_stock_pinyin_initials(name: str) -> str:
    """提取股票简称对应的拼音首字母缩写（大写），支持 ST、英文字母及多音字"""
    if not name:
        return ""
    cleaned = re.sub(r'[^\w\u4e00-\u9fa5]', '', str(name))
    tokens = pinyin(cleaned, style=Style.FIRST_LETTER)
    return "".join([t[0].upper() for t in tokens if t and t[0]])

_search_index_cache: Optional[List[Dict[str, str]]] = None

def get_or_build_search_index() -> List[Dict[str, str]]:
    """获取或构建股票拼音与简拼搜索索引"""
    global _search_index_cache
    if _search_index_cache is not None and len(_search_index_cache) > 0:
        return _search_index_cache

    universe_df = data_service.get_stock_universe()
    index_list: List[Dict[str, str]] = []
    if not universe_df.empty:
        for _, row in universe_df.iterrows():
            sym = str(row.get("symbol", "")).zfill(6)
            name = str(row.get("name", ""))
            py = get_stock_pinyin_initials(name)
            index_list.append({"s": sym, "n": name, "p": py})
    else:
        import json
        json_path = Path(__file__).resolve().parent.parent / "data" / "stocks_universe.json"
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    stocks = json.load(f)
                    for item in stocks:
                        sym = str(item.get("symbol", "")).zfill(6)
                        name = str(item.get("name", ""))
                        py = get_stock_pinyin_initials(name)
                        index_list.append({"s": sym, "n": name, "p": py})
            except Exception as e:
                logger.error("加载 stocks_universe.json 失败: %s", e)

    _search_index_cache = index_list
    logger.info("已生成股票搜索轻量拼音索引，包含 %d 支标的", len(_search_index_cache))
    return _search_index_cache

# 1. 实例化 FastAPI 核心应用
app = FastAPI(
    title=f"{APP_NAME} Mobile API",
    version=APP_VERSION,
    description="StockAI 移动端与 PWA 数据通讯接口",
)

# 允许跨域，方便局域网与调试
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. 请求与响应数据实体定义
class BuyOrderRequest(BaseModel):
    account_type: str = Field(default="MANUAL", description="操盘账户类型 MANUAL 或 AI")
    symbol: str = Field(description="6 位股票代码")
    amount: int = Field(default=100, description="买入股数，必须为 100 整数倍")
    price: Optional[float] = Field(default=None, description="自定义买入价，为空则使用现价")
    reason: Optional[str] = Field(default="手机端快捷买入", description="建仓战术理由")

class SellOrderRequest(BaseModel):
    account_type: str = Field(default="MANUAL", description="操盘账户类型 MANUAL 或 AI")
    symbol: str = Field(description="6 位股票代码")
    amount: int = Field(default=100, description="卖出股数")
    price: Optional[float] = Field(default=None, description="自定义卖出价，为空则使用现价")
    reason: Optional[str] = Field(default="手机端平仓了结", description="平仓原因")

class AutoSellRequest(BaseModel):
    account_type: str = Field(default="AI", description="巡检账户类型 MANUAL 或 AI")
    stop_loss_pct: float = Field(default=-5.0, description="硬止损比例阈值")
    take_profit_pct: float = Field(default=10.0, description="目标止盈比例阈值")
    enable_tech_breakdown: bool = Field(default=True, description="是否开启技术均线破位避险")
    enable_llm_eval: bool = Field(default=True, description="是否启用大模型操盘军规形态裁决")

class AddWatchlistRequest(BaseModel):
    symbol: str = Field(description="6 位股票代码")
    group_name: Optional[str] = Field(default="默认自选", description="所属分组名称")

# 3. 核心业务路由

@app.get("/api/system/status")
async def get_system_status() -> Dict[str, Any]:
    """获取系统运行状态与版本信息"""
    return {
        "status": "ok",
        "app_name": APP_NAME,
        "version": APP_VERSION,
    }

@app.get("/api/market/overview")
async def get_market_overview() -> Dict[str, Any]:
    """获取大盘四大核心指数与全市场涨跌统计"""
    try:
        # 获取全市场统计
        universe_df = data_service.get_stock_universe()
        if not universe_df.empty:
            up_count = int((universe_df["change_pct"] > 0).sum())
            down_count = int((universe_df["change_pct"] < 0).sum())
            flat_count = int((universe_df["change_pct"] == 0).sum())
            total_count = len(universe_df)
            avg_change = round(float(universe_df["change_pct"].mean()), 2)
        else:
            up_count, down_count, flat_count, total_count, avg_change = 0, 0, 0, 0, 0.0

        # 获取或计算核心指数行情 (上证、深成、创业板、科创50)
        indices_map = data_fetcher.fetch_specific_quotes(["sh000001", "sz399001", "sz399006", "sh000688"])
        default_names = {
            "sh000001": "上证指数",
            "sz399001": "深证成指",
            "sz399006": "创业板指",
            "sh000688": "科创50",
        }
        indices = []
        for code, def_name in default_names.items():
            info = indices_map.get(code, {})
            p = float(info.get("close_price", 0.0)) or 3000.0
            chg = float(info.get("change_pct", 0.0)) or avg_change
            indices.append({
                "code": code,
                "name": str(info.get("name") or def_name),
                "close_price": p,
                "change_pct": chg,
            })

        return {
            "indices": indices,
            "market_stats": {
                "total": total_count,
                "up": up_count,
                "down": down_count,
                "flat": flat_count,
                "avg_change": avg_change,
            }
        }
    except Exception as e:
        logger.error("移动端获取大盘概览异常: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market/rankings")
async def get_market_rankings(
    category: str = Query(default="gainers", pattern="^(gainers|losers|volume|turnover)$"),
    limit: int = Query(default=50, ge=5, le=100)
) -> List[Dict[str, Any]]:
    """获取大盘多因子排行榜（今日涨幅榜、今日跌幅榜、成交额榜、换手率榜）"""
    try:
        universe_df = data_service.get_stock_universe()
        if universe_df.empty:
            return []

        df = universe_df.copy()
        # 字段清洗与数值转换
        df["change_pct"] = pd.to_numeric(df["change_pct"], errors="coerce").fillna(0.0)
        df["price"] = pd.to_numeric(df["close_price"], errors="coerce").fillna(0.0)

        # 兼容 volume / amount
        if "amount" in df.columns:
            df["amount_num"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
        elif "volume" in df.columns:
            df["amount_num"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0.0)
        else:
            df["amount_num"] = 0.0

        if "turnover_rate" in df.columns:
            df["turnover_rate_num"] = pd.to_numeric(df["turnover_rate"], errors="coerce").fillna(0.0)
        else:
            df["turnover_rate_num"] = 0.0

        if category == "gainers":
            sorted_df = df.sort_values(by="change_pct", ascending=False)
        elif category == "losers":
            sorted_df = df.sort_values(by="change_pct", ascending=True)
        elif category == "volume":
            sorted_df = df.sort_values(by="amount_num", ascending=False)
        elif category == "turnover":
            sorted_df = df.sort_values(by="turnover_rate_num", ascending=False)
        else:
            sorted_df = df.sort_values(by="change_pct", ascending=False)

        slice_df = sorted_df.head(limit)
        results = []
        for rank, (_, row) in enumerate(slice_df.iterrows(), start=1):
            sym = str(row.get("symbol", "")).zfill(6)
            name = str(row.get("name", ""))
            price = float(row.get("price", 0.0))
            chg = float(row.get("change_pct", 0.0))
            amt = float(row.get("amount_num", 0.0))
            turnover = float(row.get("turnover_rate_num", 0.0))

            if amt >= 1e8:
                amt_str = f"{amt / 1e8:.2f} 亿"
            elif amt >= 1e4:
                amt_str = f"{amt / 1e4:.1f} 万"
            else:
                amt_str = f"{amt:.0f}"

            results.append({
                "rank": rank,
                "symbol": sym,
                "name": name,
                "price": price,
                "change_pct": chg,
                "amount_str": amt_str,
                "turnover_rate": turnover,
            })
        return results
    except Exception as e:
        logger.error("移动端获取大盘排行榜异常: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stock/search-index")
async def get_search_index():
    """获取全市场股票拼音首字母轻量索引，供前端离线/毫秒级模糊匹配"""
    try:
        index_data = get_or_build_search_index()
        return JSONResponse(
            content=index_data,
            headers={"Cache-Control": "public, max-age=3600"}
        )
    except Exception as e:
        logger.error("移动端获取股票搜索索引异常: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/watchlist")
async def get_watchlist() -> List[Dict[str, Any]]:
    """获取用户自选股列表及最新量价行情"""
    try:
        items = watchlist_service.get_watchlist_with_quotes()
        cleaned = []
        for r in items:
            cleaned.append({
                "symbol": str(r.get("symbol", "")).zfill(6),
                "name": str(r.get("name", "")),
                "price": float(r.get("close_price", 0.0) or 0.0),
                "change_pct": float(r.get("change_pct", 0.0) or 0.0),
                "turnover_rate": float(r.get("turnover_rate", 0.0) or 0.0),
                "group_name": str(r.get("group_name", "默认自选")),
            })
        return cleaned
    except Exception as e:
        logger.error("移动端获取自选股异常: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/watchlist")
async def add_watchlist(req: AddWatchlistRequest) -> Dict[str, Any]:
    """添加标的到自选股池"""
    success = watchlist_service.add_to_watchlist(req.symbol, req.group_name)
    msg = f"已成功将 {req.symbol} 加入自选股池" if success else f"添加 {req.symbol} 失败"
    return {"success": success, "message": msg}

@app.delete("/api/watchlist/{symbol}")
async def remove_watchlist(symbol: str) -> Dict[str, Any]:
    """自选股池移除标的"""
    success = watchlist_service.remove_from_watchlist(symbol)
    msg = f"已成功将 {symbol} 移出自选股池" if success else f"移除 {symbol} 失败"
    return {"success": success, "message": msg}

@app.get("/api/recommend")
async def get_recommendations() -> Dict[str, Any]:
    """获取 AI 智能精选推荐标的列表"""
    try:
        res = recommend_service.generate_recommendations(top_n=5)
        return {
            "market_summary": res.market_summary,
            "stocks": [
                {
                    "symbol": s.symbol,
                    "name": s.name,
                    "score": s.score,
                    "reasons": s.reasons,
                    "risk_warnings": s.risk_warnings,
                }
                for s in res.recommended_stocks
            ]
        }
    except Exception as e:
        logger.error("移动端获取精选推荐异常: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/trading/summary")
async def get_trading_summary(account_type: str = "MANUAL") -> Dict[str, Any]:
    """获取交易账户总览（总资产、可用现金、持仓市值、总浮盈）"""
    try:
        summary = trading_service.get_account_summary(account_type.upper())
        # 双向兼顾命名规范
        eq = float(summary.get("total_equity", 0.0))
        pnl = float(summary.get("floating_pnl", 0.0))
        mkt = float(summary.get("market_value", 0.0))
        cash = float(summary.get("available_cash", 0.0))
        ret = float(summary.get("total_return_pct", 0.0))
        
        return {
            "account_type": account_type.upper(),
            "total_asset": eq,
            "total_equity": eq,
            "available_cash": cash,
            "holding_market_val": mkt,
            "market_value": mkt,
            "float_pnl": pnl,
            "floating_pnl": pnl,
            "total_return_pct": ret,
            "position_count": summary.get("position_count", 0),
        }
    except Exception as e:
        logger.error("移动端获取账户总览异常: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/trading/positions")
async def get_trading_positions(account_type: str = "MANUAL") -> List[Dict[str, Any]]:
    """获取当前持仓明细（0 延迟秒开读取）"""
    try:
        # 先快速读取本地数据库记录
        positions = trading_service.get_positions(account_type.upper())
        return positions
    except Exception as e:
        logger.error("移动端获取持仓列表异常: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/trading/refresh-quotes")
async def refresh_trading_quotes(account_type: str = "MANUAL") -> Dict[str, Any]:
    """定向极速刷新持仓最新价格盘口"""
    try:
        trading_service.refresh_positions_quotes(account_type.upper())
        return {"success": True}
    except Exception as e:
        logger.error("移动端定向刷新持仓价格异常: %s", e)
        return {"success": False, "error": str(e)}

@app.get("/api/trading/comparison")
async def get_trading_comparison() -> Dict[str, Any]:
    """获取人机双轨账户（人类主观 vs AI 智能）收益与资产对比数据"""
    try:
        manual_sum = trading_service.get_account_summary("MANUAL")
        ai_sum = trading_service.get_account_summary("AI")
        return {
            "manual": {
                "account_name": "人类主观操盘",
                "total_equity": float(manual_sum.get("total_equity", 100000.0)),
                "total_return_pct": float(manual_sum.get("total_return_pct", 0.0)),
                "position_count": manual_sum.get("position_count", 0),
                "available_cash": float(manual_sum.get("available_cash", 100000.0)),
                "floating_pnl": float(manual_sum.get("floating_pnl", 0.0)),
            },
            "ai": {
                "account_name": "AI 智能操盘",
                "total_equity": float(ai_sum.get("total_equity", 100000.0)),
                "total_return_pct": float(ai_sum.get("total_return_pct", 0.0)),
                "position_count": ai_sum.get("position_count", 0),
                "available_cash": float(ai_sum.get("available_cash", 100000.0)),
                "floating_pnl": float(ai_sum.get("floating_pnl", 0.0)),
            }
        }
    except Exception as e:
        logger.error("移动端获取人机操盘对比异常: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/trading/skills")
async def get_trading_skills() -> List[Dict[str, Any]]:
    """获取 AI 操盘手实战反思沉淀的交易技能与军规库"""
    try:
        skills = skill_engine.list_all_skills()
        return skills
    except Exception as e:
        logger.error("移动端获取操盘军规技能列表异常: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/trading/auto-trade")
async def execute_auto_trade(max_buy_count: int = 2) -> Dict[str, Any]:
    """触发 AI 一键自动计算与多因子建仓管线"""
    try:
        res = auto_trader.execute_auto_trading(account_type="AI", max_buy_count=max_buy_count)
        return res
    except Exception as e:
        logger.error("移动端执行 AI 自动建仓异常: %s", e)
        return {"success": False, "msg": f"AI 自动建仓异常: {str(e)}", "bought_items": [], "executed_count": 0}

@app.post("/api/trading/auto-sell")
async def execute_auto_sell(req: Optional[AutoSellRequest] = None) -> Dict[str, Any]:
    """触发 AI 持仓智能巡检与自动平仓决策管线"""
    try:
        acc_type = (req.account_type if req and req.account_type else "AI").upper()
        stop_loss = req.stop_loss_pct if req else -5.0
        take_profit = req.take_profit_pct if req else 10.0
        enable_tech = req.enable_tech_breakdown if req else True
        enable_llm = req.enable_llm_eval if req else True

        res = auto_trader.execute_auto_selling(
            account_type=acc_type,
            stop_loss_pct=stop_loss,
            take_profit_pct=take_profit,
            enable_tech_breakdown=enable_tech,
            enable_llm_eval=enable_llm
        )
        return res
    except Exception as e:
        logger.error("移动端执行 AI 自动巡检平仓异常: %s", e)
        return {
            "success": False,
            "msg": f"AI 自动巡检平仓异常: {str(e)}",
            "sold_items": [],
            "held_items": [],
            "locked_items": [],
            "sold_count": 0
        }

@app.post("/api/trading/buy")
async def execute_buy(req: BuyOrderRequest) -> Dict[str, Any]:
    """模拟市价/指定价买入建仓"""
    try:
        target_account = (req.account_type or "MANUAL").upper()
        success, msg = trading_service.buy_stock(
            account_type=target_account,
            symbol=req.symbol,
            amount=req.amount,
            custom_price=req.price,
            reason=req.reason
        )
        return {"success": success, "message": msg}
    except Exception as e:
        logger.error("移动端买入建仓异常: %s", e)
        return {"success": False, "message": f"建仓失败: {str(e)}"}

@app.post("/api/trading/close")
async def execute_close(req: SellOrderRequest) -> Dict[str, Any]:
    """模拟一键平仓卖出"""
    try:
        target_account = (req.account_type or "MANUAL").upper()
        success, msg, trade_detail = trading_service.sell_stock(
            account_type=target_account,
            symbol=req.symbol,
            amount=req.amount,
            custom_price=req.price,
            reason=req.reason
        )
        return {"success": success, "message": msg, "trade_detail": trade_detail}
    except Exception as e:
        logger.error("移动端平仓异常: %s", e)
        return {"success": False, "message": f"平仓失败: {str(e)}"}

@app.get("/api/stock/{symbol}/kline")
async def get_stock_kline(symbol: str, count: int = 60) -> Dict[str, Any]:
    """获取个股近期日 K 线历史数据与常用均线"""
    try:
        df = data_service.get_stock_kline_with_indicators(symbol, count=count)
        if df.empty:
            return {"symbol": symbol, "klines": []}
        
        klines = []
        for _, row in df.iterrows():
            date_str = str(row.get("date", ""))[:10]
            c = float(row.get("close", 0.0))
            o = float(row.get("open", c))
            h = float(row.get("high", max(o, c)))
            l = float(row.get("low", min(o, c)))
            v = float(row.get("volume", 0.0))
            ma5 = float(row.get("ma5", c)) if not pd.isna(row.get("ma5")) else c
            ma10 = float(row.get("ma10", c)) if not pd.isna(row.get("ma10")) else c
            ma20 = float(row.get("ma20", c)) if not pd.isna(row.get("ma20")) else c

            klines.append({
                "date": date_str,
                "open": o,
                "close": c,
                "high": h,
                "low": l,
                "volume": v,
                "ma5": round(ma5, 2),
                "ma10": round(ma10, 2),
                "ma20": round(ma20, 2),
            })
        return {"symbol": symbol, "klines": klines}
    except Exception as e:
        logger.error("移动端获取 K 线数据异常: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

# 4. 挂载静态文件目录 (PWA 核心资产)
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
