# -*- coding: utf-8 -*-
"""AI 自主操盘节律调度引擎与全局急停断电单元测试套件"""

import pytest
from datetime import datetime, time
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.services.scheduler_service import scheduler_service, SchedulerState
from app.web.api import app

client = TestClient(app)


def setup_function():
    """每个测试前重置调度器状态至就绪待命"""
    scheduler_service.reset_emergency_stop()
    scheduler_service.pause()


def test_scheduler_initial_state():
    """测试调度引擎单例状态与基础指标"""
    status = scheduler_service.get_status()
    assert "state" in status
    assert "is_active" in status
    assert "is_emergency" in status
    assert "audit_logs" in status
    assert isinstance(status["audit_logs"], list)


def test_scheduler_state_transitions():
    """测试状态机转换：启动 -> 暂停 -> 急停 -> 解除"""
    # 1. 启动
    scheduler_service.start()
    assert scheduler_service.state == SchedulerState.RUNNING
    assert scheduler_service.is_active is True

    # 2. 暂停
    scheduler_service.pause()
    assert scheduler_service.state == SchedulerState.PAUSED
    assert scheduler_service.is_active is False

    # 3. 触发急停
    scheduler_service.emergency_stop(reason="单元测试模拟熔断")
    assert scheduler_service.state == SchedulerState.EMERGENCY
    assert scheduler_service.is_active is False
    assert scheduler_service.is_emergency is True

    # 4. 急停状态下尝试启动应被拒绝
    scheduler_service.start()
    assert scheduler_service.state == SchedulerState.EMERGENCY

    # 5. 解除急停
    scheduler_service.reset_emergency_stop()
    assert scheduler_service.state == SchedulerState.STOPPED
    assert scheduler_service.is_emergency is False


def test_trade_time_judgment():
    """测试 A 股早盘、午盘及非交易时间判定"""
    # 早盘交易时段 09:45
    t_morning = datetime(2026, 9, 21, 9, 45, 0)
    assert scheduler_service.is_trade_time(t_morning) is True

    # 午盘交易时段 13:30
    t_afternoon = datetime(2026, 9, 21, 13, 30, 0)
    assert scheduler_service.is_trade_time(t_afternoon) is True

    # 中午休市 12:00
    t_noon = datetime(2026, 9, 21, 12, 0, 0)
    assert scheduler_service.is_trade_time(t_noon) is False

    # 夜间非交易 20:00
    t_night = datetime(2026, 9, 21, 20, 0, 0)
    assert scheduler_service.is_trade_time(t_night) is False


def test_trade_day_judgment():
    """测试周一至周五与周末的交易日判定"""
    # 周一 (weekday == 0)
    mon = datetime(2026, 9, 21, 10, 0, 0)
    assert scheduler_service.is_trade_day(mon) is True

    # 周六 (weekday == 5)
    sat = datetime(2026, 9, 26, 10, 0, 0)
    assert scheduler_service.is_trade_day(sat) is False

    # 周日 (weekday == 6)
    sun = datetime(2026, 9, 27, 10, 0, 0)
    assert scheduler_service.is_trade_day(sun) is False


def test_phase_info_description():
    """测试交易各阶段文本描述生成"""
    # 盘前准备
    t_pre = datetime(2026, 9, 21, 9, 10, 0)
    info_pre = scheduler_service.get_current_phase_info(t_pre)
    assert "盘前准备" in info_pre.get("phase_name", "") or "早盘进攻" in info_pre.get("next_action", "")

    # 尾盘定型
    t_tail = datetime(2026, 9, 21, 14, 45, 0)
    info_tail = scheduler_service.get_current_phase_info(t_tail)
    assert "尾盘定型" in info_tail.get("phase_name", "") or "尾盘" in info_tail.get("next_action", "")

    # 盘后复盘
    t_post = datetime(2026, 9, 21, 15, 30, 0)
    info_post = scheduler_service.get_current_phase_info(t_post)
    assert "复盘" in info_post.get("phase_name", "") or "复盘" in info_post.get("next_action", "")


def test_api_scheduler_status():
    """测试 FastAPI 接口获取调度器状态"""
    resp = client.get("/api/trading/scheduler/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "state" in data["data"]
    assert "is_active" in data["data"]


def test_api_scheduler_toggle():
    """测试 FastAPI 接口启动与暂停托管"""
    # 启动
    resp_start = client.post("/api/trading/scheduler/toggle", json={"action": "start"})
    assert resp_start.status_code == 200
    assert resp_start.json()["data"]["state"] == "RUNNING"

    # 暂停
    resp_pause = client.post("/api/trading/scheduler/toggle", json={"action": "pause"})
    assert resp_pause.status_code == 200
    assert resp_pause.json()["data"]["state"] == "PAUSED"


def test_api_emergency_stop_and_reset():
    """测试 FastAPI 接口触发急停与解除急停"""
    # 触发急停
    resp_kill = client.post(
        "/api/trading/scheduler/emergency-stop",
        json={"reason": "接口急停断电测试"}
    )
    assert resp_kill.status_code == 200
    data_kill = resp_kill.json()
    assert data_kill["data"]["state"] == "EMERGENCY"
    assert data_kill["data"]["is_emergency"] is True

    # 解除急停
    resp_reset = client.post("/api/trading/scheduler/reset-emergency")
    assert resp_reset.status_code == 200
    data_reset = resp_reset.json()
    assert data_reset["data"]["is_emergency"] is False
    assert data_reset["data"]["state"] == "STOPPED"
