# -*- coding: utf-8 -*-
"""测试 HTTP Basic 身份验证中间件 (公网暴露安全防护)"""

import os
import base64
import pytest
from starlette.testclient import TestClient

from app.web.api import app


@pytest.fixture
def client():
    return TestClient(app)


def test_auth_disabled_by_default(client):
    """测试默认未开启身份验证时正常访问"""
    os.environ["STOCKAI_ENABLE_AUTH"] = "false"
    response = client.get("/api/system/status")
    assert response.status_code == 200


def test_auth_enabled_unauthorized(client):
    """测试开启身份验证后无凭证访问返回 401"""
    os.environ["STOCKAI_ENABLE_AUTH"] = "true"
    os.environ["STOCKAI_AUTH_USER"] = "admin"
    os.environ["STOCKAI_AUTH_PASS"] = "secret123"

    try:
        response = client.get("/api/system/status")
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers
        assert 'Basic realm="StockAI Secure Trading"' in response.headers["WWW-Authenticate"]
    finally:
        os.environ["STOCKAI_ENABLE_AUTH"] = "false"


def test_auth_enabled_wrong_credentials(client):
    """测试开启身份验证后错误凭证访问返回 401"""
    os.environ["STOCKAI_ENABLE_AUTH"] = "true"
    os.environ["STOCKAI_AUTH_USER"] = "admin"
    os.environ["STOCKAI_AUTH_PASS"] = "secret123"

    try:
        bad_token = base64.b64encode(b"admin:wrongpassword").decode("utf-8")
        headers = {"Authorization": f"Basic {bad_token}"}
        response = client.get("/api/system/status", headers=headers)
        assert response.status_code == 401
        assert "Invalid Credentials" in response.text
    finally:
        os.environ["STOCKAI_ENABLE_AUTH"] = "false"


def test_auth_enabled_valid_credentials(client):
    """测试开启身份验证后正确凭证访问返回 200"""
    os.environ["STOCKAI_ENABLE_AUTH"] = "true"
    os.environ["STOCKAI_AUTH_USER"] = "admin"
    os.environ["STOCKAI_AUTH_PASS"] = "secret123"

    try:
        token = base64.b64encode(b"admin:secret123").decode("utf-8")
        headers = {"Authorization": f"Basic {token}"}
        response = client.get("/api/system/status", headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    finally:
        os.environ["STOCKAI_ENABLE_AUTH"] = "false"


def test_auth_options_preflight(client):
    """测试 OPTIONS 预检请求即使开启验证也放行"""
    os.environ["STOCKAI_ENABLE_AUTH"] = "true"
    os.environ["STOCKAI_AUTH_USER"] = "admin"
    os.environ["STOCKAI_AUTH_PASS"] = "secret123"

    try:
        headers = {
            "Origin": "http://113.98.232.83:2222",
            "Access-Control-Request-Method": "GET"
        }
        response = client.options("/api/system/status", headers=headers)
        assert response.status_code == 200
    finally:
        os.environ["STOCKAI_ENABLE_AUTH"] = "false"
