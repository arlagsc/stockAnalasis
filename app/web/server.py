# -*- coding: utf-8 -*-
"""StockAI 移动端 Web 服务器启动与局域网探针管理

负责自动检测本机活跃局域网 IP、生成控制台 ASCII 与 Base64 图片二维码、
启动与管理轻量级 Uvicorn Web 服务，支持单机命令行启动与桌面客户端嵌入式守护。
"""

import socket
import io
import base64
import threading
import uvicorn
from typing import Tuple, Optional
import qrcode

from app.core.config import logger

class MobileServerManager:
    """移动端服务生命周期管理器"""

    _server_thread: Optional[threading.Thread] = None
    _server_instance: Optional[uvicorn.Server] = None
    _is_running: bool = False

    @staticmethod
    def get_local_ip() -> str:
        """获取当前机器在局域网中的真实 IP 地址"""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # 建立假连接以确定出网路由选择的局域网 IP
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = "127.0.0.1"
        finally:
            s.close()
        return ip

    @classmethod
    def get_access_urls(cls, port: int = 8000) -> Tuple[str, str]:
        """返回本机局域网访问地址与本地回环地址"""
        local_ip = cls.get_local_ip()
        lan_url = f"http://{local_ip}:{port}"
        loopback_url = f"http://127.0.0.1:{port}"
        return lan_url, loopback_url

    @classmethod
    def print_ascii_qr(cls, url: str):
        """在控制台直接打印清晰的 ASCII 二维码"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=1,
            border=1,
        )
        qr.add_data(url)
        qr.make(fit=True)
        print("\n" + "=" * 54)
        print("请使用 iPhone 相机或微信扫描下方二维码直达：")
        print(f"局域网访问链接: {url}")
        print("=" * 54 + "\n")
        try:
            qr.print_ascii(invert=True)
        except Exception:
            pass
        print("\n" + "=" * 54 + "\n")

    @classmethod
    def generate_qr_base64(cls, url: str) -> str:
        """生成供 Qt 界面显示的 Base64 格式 PNG 二维码图片"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=6,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#38BDF8", back_color="#0F1115")
        
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64_str}"

    @classmethod
    def start(cls, host: str = "0.0.0.0", port: int = 8000, blocking: bool = False):
        """启动移动端 FastAPI Web 服务"""
        if cls._is_running:
            logger.info("移动端 Web 服务已在运行中，无需重复启动。")
            return

        lan_url, _ = cls.get_access_urls(port)
        logger.info("正在启动 StockAI iPhone 移动端服务，绑定: %s:%d ...", host, port)
        logger.info("iPhone 同局域网访问地址: %s", lan_url)

        config = uvicorn.Config(
            app="app.web.api:app",
            host=host,
            port=port,
            log_level="warning",
            loop="asyncio",
        )
        cls._server_instance = uvicorn.Server(config)
        cls._is_running = True

        if blocking:
            cls.print_ascii_qr(lan_url)
            cls._server_instance.run()
        else:
            cls._server_thread = threading.Thread(
                target=cls._server_instance.run,
                daemon=True,
                name="MobileServerThread"
            )
            cls._server_thread.start()
            logger.info("移动端 Web 守护线程已在后台启动完成。")

    @classmethod
    def stop(cls):
        """停止移动端 Web 服务"""
        if cls._server_instance and cls._is_running:
            logger.info("正在关闭移动端 Web 服务...")
            cls._server_instance.should_exit = True
            cls._is_running = False
            cls._server_instance = None
            logger.info("移动端 Web 服务已安全停止。")

    @classmethod
    def is_running(cls) -> bool:
        """检查服务当前是否正在运行"""
        return cls._is_running

mobile_server = MobileServerManager
