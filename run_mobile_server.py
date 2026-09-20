# -*- coding: utf-8 -*-
"""StockAI iPhone 移动端局域网服务启动入口

执行此脚本将在本机启动轻量级 FastAPI Web 服务，
并自动检测本机局域网 IP、输出终端二维码与访问链接。
在同一 Wi-Fi 下使用 iPhone 相机或微信扫码即可直接在 Safari 中打开，
并可点击「分享 -> 添加到主屏幕」作为全屏 App 体验。

使用方法:
    python run_mobile_server.py [--port 8000] [--host 0.0.0.0]
"""

import sys
import argparse
from app.web.server import mobile_server
from app.core.config import logger, APP_NAME, APP_VERSION

def main():
    parser = argparse.ArgumentParser(description=f"{APP_NAME} 移动端局域网 Web/PWA 服务")
    parser.add_argument("--host", default="0.0.0.0", help="监听网络接口 (默认: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="服务端口 (默认: 8000)")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print(f"正在启动 {APP_NAME} v{APP_VERSION} iPhone 移动端服务...")
    print("=" * 60)

    try:
        mobile_server.start(host=args.host, port=args.port, blocking=True)
    except KeyboardInterrupt:
        print("\n收到退出指令，正在关闭服务...")
        mobile_server.stop()
        print("服务已安全退出。")
        sys.exit(0)

if __name__ == "__main__":
    main()
