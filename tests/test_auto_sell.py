# -*- coding: utf-8 -*-
"""AI 自动巡检与智能平仓单元测试套件"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.services.auto_trader import auto_trader
from app.services.trading_service import trading_service
from app.ai.skill_engine import skill_engine
from app.web.api import app

client = TestClient(app)


def test_auto_sell_empty_positions():
    """测试当前账户无任何持仓时，巡检平仓返回优雅提示"""
    with patch.object(trading_service, "get_positions", return_value=[]):
        with patch.object(trading_service, "refresh_positions_quotes", return_value=None):
            res = auto_trader.execute_auto_selling(account_type="AI")
            assert res["success"] is True
            assert res["sold_count"] == 0
            assert "无需执行" in res["msg"]
            assert len(res["sold_items"]) == 0


def test_auto_sell_t1_lock_protection():
    """测试 T+1 锁定期持仓被严格锁止，绝不被平仓"""
    mock_pos = [
        {
            "symbol": "000001",
            "name": "平安银行",
            "total_amount": 500,
            "available_amount": 0,  # T+1 锁定中
            "cost_price": 10.0,
            "current_price": 9.0,
            "floating_pnl": -500.0,
            "floating_pnl_pct": -10.0,  # 虽已达 -10%，但 T+1 锁定绝不能卖
        }
    ]
    with patch.object(trading_service, "get_positions", return_value=mock_pos):
        with patch.object(trading_service, "refresh_positions_quotes", return_value=None):
            res = auto_trader.execute_auto_selling(account_type="AI", stop_loss_pct=-5.0)
            assert res["success"] is True
            assert res["sold_count"] == 0
            assert len(res["sold_items"]) == 0
            assert len(res["locked_items"]) == 1
            assert res["locked_items"][0]["symbol"] == "000001"
            assert "T+1 锁定中" in res["locked_items"][0]["status"]


def test_auto_sell_stop_loss_trigger():
    """测试浮亏达到止损线时自动执行平仓"""
    mock_pos = [
        {
            "symbol": "000002",
            "name": "万科A",
            "total_amount": 1000,
            "available_amount": 1000,  # 可卖
            "cost_price": 10.0,
            "current_price": 9.4,
            "floating_pnl": -600.0,
            "floating_pnl_pct": -6.0,  # 达到止损线 -5.0%
        }
    ]
    fake_trade_summary = {
        "symbol": "000002",
        "name": "万科A",
        "action": "SELL",
        "sell_price": 9.4,
        "cost_price": 10.0,
        "amount": 1000,
        "realized_pnl": -600.0,
        "realized_pct": -6.0,
        "reason": "硬止损",
    }
    with patch.object(trading_service, "get_positions", return_value=mock_pos):
        with patch.object(trading_service, "refresh_positions_quotes", return_value=None):
            with patch.object(trading_service, "sell_stock", return_value=(True, "平仓成功", fake_trade_summary)):
                with patch.object(skill_engine, "reflect_on_trade", return_value=None):
                    res = auto_trader.execute_auto_selling(account_type="AI", stop_loss_pct=-5.0, enable_llm_eval=False)
                    assert res["success"] is True
                    assert res["sold_count"] == 1
                    assert len(res["sold_items"]) == 1
                    sold = res["sold_items"][0]
                    assert sold["symbol"] == "000002"
                    assert sold["trigger_type"] == "硬止损风控"
                    assert sold["realized_pnl"] == -600.0


def test_auto_sell_take_profit_trigger():
    """测试浮盈达到目标止盈线时自动执行平仓锁定利润"""
    mock_pos = [
        {
            "symbol": "600519",
            "name": "贵州茅台",
            "total_amount": 100,
            "available_amount": 100,
            "cost_price": 1500.0,
            "current_price": 1680.0,
            "floating_pnl": 18000.0,
            "floating_pnl_pct": 12.0,  # 超过止盈线 +10.0%
        }
    ]
    fake_trade_summary = {
        "symbol": "600519",
        "name": "贵州茅台",
        "action": "SELL",
        "sell_price": 1680.0,
        "cost_price": 1500.0,
        "amount": 100,
        "realized_pnl": 18000.0,
        "realized_pct": 12.0,
        "reason": "波段止盈",
    }
    with patch.object(trading_service, "get_positions", return_value=mock_pos):
        with patch.object(trading_service, "refresh_positions_quotes", return_value=None):
            with patch.object(trading_service, "sell_stock", return_value=(True, "平仓成功", fake_trade_summary)):
                with patch.object(skill_engine, "reflect_on_trade", return_value=None):
                    res = auto_trader.execute_auto_selling(account_type="AI", take_profit_pct=10.0, enable_llm_eval=False)
                    assert res["success"] is True
                    assert res["sold_count"] == 1
                    assert len(res["sold_items"]) == 1
                    sold = res["sold_items"][0]
                    assert sold["symbol"] == "600519"
                    assert sold["trigger_type"] == "动态止盈获利"
                    assert sold["realized_pnl"] == 18000.0


def test_auto_sell_healthy_held():
    """测试未触发止损止盈且技术形态健康的持仓保持持有"""
    mock_pos = [
        {
            "symbol": "002429",
            "name": "兆驰股份",
            "total_amount": 2000,
            "available_amount": 2000,
            "cost_price": 5.0,
            "current_price": 5.15,
            "floating_pnl": 300.0,
            "floating_pnl_pct": 3.0,  # 适度浮盈 3%，健康持有
        }
    ]
    with patch.object(trading_service, "get_positions", return_value=mock_pos):
        with patch.object(trading_service, "refresh_positions_quotes", return_value=None):
            res = auto_trader.execute_auto_selling(
                account_type="AI",
                stop_loss_pct=-5.0,
                take_profit_pct=10.0,
                enable_tech_breakdown=False,
                enable_llm_eval=False
            )
            assert res["success"] is True
            assert res["sold_count"] == 0
            assert len(res["held_items"]) == 1
            assert res["held_items"][0]["symbol"] == "002429"
            assert "继续持有" in res["held_items"][0]["status"]


def test_auto_sell_api_endpoint():
    """测试 POST /api/trading/auto-sell 接口响应规范"""
    with patch.object(auto_trader, "execute_auto_selling", return_value={
        "success": True,
        "msg": "AI 巡检完成",
        "sold_items": [],
        "held_items": [],
        "locked_items": [],
        "sold_count": 0
    }):
        resp = client.post("/api/trading/auto-sell", json={
            "account_type": "AI",
            "stop_loss_pct": -5.0,
            "take_profit_pct": 10.0
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "sold_items" in data
        assert "held_items" in data
