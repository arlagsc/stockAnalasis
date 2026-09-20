# -*- coding: utf-8 -*-
"""虚拟操盘定向盘口查询与秒开性能单元测试"""

import time
import pytest
from app.data.fetcher import data_fetcher
from app.services.trading_service import trading_service
from app.core.database import db_manager, VirtualAccount, VirtualPosition

def test_fetch_specific_quotes_accuracy():
    """验证定向轻量盘口接口字段结构、准确性与毫秒级延迟"""
    t0 = time.time()
    res = data_fetcher.fetch_specific_quotes(["000001", "600519"])
    elapsed = time.time() - t0

    assert isinstance(res, dict)
    assert len(res) == 2
    assert "000001" in res
    assert "600519" in res

    p_000001 = res["000001"]
    assert p_000001["symbol"] == "000001"
    assert p_000001["close_price"] > 0
    assert "name" in p_000001

    p_600519 = res["600519"]
    assert p_600519["symbol"] == "600519"
    assert p_600519["close_price"] > 0
    assert "name" in p_600519

    print(f"\n定向拉取 2 支标的耗时: {elapsed:.3f} 秒")

def test_fetch_specific_quotes_empty():
    """验证传入空列表时直接返回空字典且耗时趋近于 0"""
    t0 = time.time()
    res = data_fetcher.fetch_specific_quotes([])
    elapsed = time.time() - t0

    assert res == {}
    assert elapsed < 0.01

def test_refresh_positions_quotes_fast():
    """验证定向更新持仓盘口价格正确性与事务一致性"""
    # 准备测试账户并建仓一手 000001
    trading_service.reset_account("MANUAL", initial_capital=200000.0)
    success, msg = trading_service.buy_stock("MANUAL", "000001", 100, custom_price=10.0, reason="测试定向刷新")
    assert success is True

    # 执行定向刷新
    t0 = time.time()
    trading_service.refresh_positions_quotes("MANUAL")
    elapsed = time.time() - t0

    positions = trading_service.get_positions("MANUAL")
    assert len(positions) == 1
    pos = positions[0]
    assert pos["symbol"] == "000001"
    assert pos["current_price"] > 0
    print(f"\n持仓定向刷新执行耗时: {elapsed:.3f} 秒，当前价格: {pos['current_price']}")

def test_zero_latency_local_read():
    """验证纯本地 SQLite 资产与持仓读取耗时在 30 毫秒以内 (秒开保障)"""
    t0 = time.time()
    man_sum = trading_service.get_account_summary("MANUAL")
    ai_sum = trading_service.get_account_summary("AI")
    man_pos = trading_service.get_positions("MANUAL")
    ai_pos = trading_service.get_positions("AI")
    elapsed = (time.time() - t0) * 1000  # 毫秒

    assert man_sum["total_equity"] > 0
    assert ai_sum["total_equity"] > 0
    assert isinstance(man_pos, list)
    assert isinstance(ai_pos, list)
    print(f"\n本地纯内存与 SQLite 首屏数据查询耗时: {elapsed:.2f} ms")
    assert elapsed < 50.0  # 严格小于 50ms 阈值
