# -*- coding: utf-8 -*-
"""StockAI 生产级独立 Web 服务与自动操盘守护进程启动入口

用法示例:
    # 默认监听 0.0.0.0:2222，开启安全认证与后台交易时钟调度
    python run_server.py --port 2222 --auth-user admin --auth-pass MyPassword123

    # 无认证局域网测试
    python run_server.py --port 8000 --no-auth
"""

import sys
import os
import signal
import socket
import argparse
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import logger, APP_NAME, APP_VERSION
from app.services.scheduler_service import scheduler_service
from app.web.api import app
import uvicorn

def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """探测指定端口是否已被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0

def parse_args():
    parser = argparse.ArgumentParser(description=f"{APP_NAME} v{APP_VERSION} Web Server & Scheduler Daemon")
    parser.add_argument("--host", default=os.getenv("STOCKAI_HOST", "0.0.0.0"), help="绑定监听网络地址 (默认: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=int(os.getenv("STOCKAI_PORT", "2222")), help="绑定监听端口 (默认: 2222)")
    parser.add_argument("--auth-user", default=os.getenv("STOCKAI_AUTH_USER", "admin"), help="HTTP Basic 认证用户名 (默认: admin)")
    parser.add_argument("--auth-pass", default=os.getenv("STOCKAI_AUTH_PASS", ""), help="HTTP Basic 认证密码")
    parser.add_argument("--no-auth", action="store_true", help="禁用 HTTP Basic 认证")
    parser.add_argument("--no-scheduler", action="store_true", help="禁用自动交易时钟调度器")
    parser.add_argument("--account-type", default="AI", help="自动托管操盘账户类型 (默认: AI)")
    return parser.parse_args()

def setup_signal_handlers():
    """注册优雅退出信号处理器"""
    def handle_exit(sig, frame):
        logger.info("捕获停机信号 (%s)，正在安全停止交易调度守护进程...", sig)
        try:
            scheduler_service.pause()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

def main():
    args = parse_args()
    setup_signal_handlers()

    print("=" * 60)
    print(f">>> 启动 {APP_NAME} v{APP_VERSION} 生产级 Web 操盘工作台服务 <<<")
    print("=" * 60)
    print(f"监听地址: http://{args.host}:{args.port}")

    # 1. 配置安全认证环境变量
    enable_auth = not args.no_auth and bool(args.auth_user and args.auth_pass)
    if enable_auth:
        os.environ["STOCKAI_ENABLE_AUTH"] = "true"
        os.environ["STOCKAI_AUTH_USER"] = args.auth_user
        os.environ["STOCKAI_AUTH_PASS"] = args.auth_pass
        print(f"安全认证: [已开启] HTTP Basic Auth (用户: {args.auth_user})")
    else:
        os.environ["STOCKAI_ENABLE_AUTH"] = "false"
        if not args.no_auth and not args.auth_pass:
            print("安全提示: 未指定 --auth-pass，已自动降级为免认证模式 (仅建议内网调试使用)")
        else:
            print("安全认证: [已禁用] 免密访问")

    # 2. 检查端口占用
    if is_port_in_use(args.port, host="127.0.0.1"):
        logger.warning("端口 %d 当前已被占用！若已有 StockAIService 在运行，可直接通过浏览器访问。", args.port)
        print(f"[警告] 本地端口 {args.port} 已被占用，请确认是否已有实例在运行。")

    # 3. 启动后台交易时钟守护引擎
    if not args.no_scheduler:
        try:
            ok = scheduler_service.start(account_type=args.account_type)
            if ok:
                logger.info("AutonomousScheduler 交易节律守护引擎已随 Web 服务联动自启动 (账户: %s)", args.account_type)
                print(f"交易守护: [已启动] 自动操盘节律常驻监听中 (账户: {args.account_type})")
            else:
                logger.warning("AutonomousScheduler 启动受阻，当前可能处于急停或休止状态")
        except Exception as e:
            logger.error("启动自动交易调度引擎异常: %s", e)
    else:
        print("交易守护: [未启用]")

    print("-" * 60)
    print(f"服务就绪！公网映射地址: http://113.98.232.83:{args.port}")
    print("按 Ctrl+C 可安全停止服务")
    print("=" * 60)

    # 4. 驱动 Uvicorn ASGI 服务
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
        access_log=True,
    )

if __name__ == "__main__":
    main()
