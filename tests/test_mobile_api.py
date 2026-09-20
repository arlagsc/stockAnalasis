# -*- coding: utf-8 -*-
"""StockAI iPhone 移动端与 PWA API 自动化集成测试"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.web.api import app

@pytest.mark.anyio
async def test_system_status():
    """测试系统状态与版本返回"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/system/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

@pytest.mark.anyio
async def test_market_overview():
    """测试大盘四大指数与多空分布统计"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/market/overview")
        assert response.status_code == 200
        data = response.json()
        assert "indices" in data
        assert "market_stats" in data
        assert data["market_stats"]["total"] >= 0

@pytest.mark.anyio
async def test_watchlist_api():
    """测试自选股获取接口"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/watchlist")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

@pytest.mark.anyio
async def test_trading_summary_and_positions():
    """测试虚拟操盘资产看板与持仓明细"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 资产概况
        res_sum = await client.get("/api/trading/summary?account_type=MANUAL")
        assert res_sum.status_code == 200
        sum_data = res_sum.json()
        assert "total_asset" in sum_data
        assert "available_cash" in sum_data

        # 2. 持仓列表
        res_pos = await client.get("/api/trading/positions?account_type=MANUAL")
        assert res_pos.status_code == 200
        pos_data = res_pos.json()
        assert isinstance(pos_data, list)

@pytest.mark.anyio
async def test_kline_api():
    """测试技术面 K 线接口"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/stock/002429/kline?count=30")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "002429"
        assert "klines" in data

@pytest.mark.anyio
async def test_pwa_static_assets():
    """测试 PWA 核心静态资源可访问性"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 首页
        res_index = await client.get("/")
        assert res_index.status_code == 200
        assert "StockAI" in res_index.text

        # manifest.json
        res_manifest = await client.get("/manifest.json")
        assert res_manifest.status_code == 200
        manifest = res_manifest.json()
        assert manifest["short_name"] == "StockAI"
        assert manifest["display"] == "standalone"

        # CSS 样式
        res_css = await client.get("/css/style.css")
        assert res_css.status_code == 200

        # JS 脚本
        res_js = await client.get("/js/app.js")
        assert res_js.status_code == 200

@pytest.mark.anyio
async def test_search_index_api():
    """测试拼音首字母搜索轻量索引接口"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/stock/search-index")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # 验证包含三元组字段
        first = data[0]
        assert "s" in first
        assert "n" in first
        assert "p" in first
        # 验证至少存在平安银行等标的的拼音首字母
        symbols_map = {item["s"]: item for item in data}
        if "000001" in symbols_map:
            assert symbols_map["000001"]["p"] == "PAYH"
        if "600519" in symbols_map:
            assert symbols_map["600519"]["p"] == "GZMT"

@pytest.mark.anyio
async def test_market_rankings_api():
    """测试全景大盘 4 大排行榜接口"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for cat in ["gainers", "losers", "volume", "turnover"]:
            response = await client.get(f"/api/market/rankings?category={cat}&limit=10")
            assert response.status_code == 200
            list_data = response.json()
            assert isinstance(list_data, list)
            if len(list_data) > 0:
                item = list_data[0]
                assert item["rank"] == 1
                assert "symbol" in item
                assert "name" in item
                assert "price" in item
                assert "change_pct" in item
                assert "amount_str" in item
                assert "turnover_rate" in item
