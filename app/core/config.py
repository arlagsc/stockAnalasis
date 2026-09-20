# -*- coding: utf-8 -*-
"""系统全局配置与路径管理模块

定义应用程序运行时的核心配置、文件存储路径、默认模型参数与网络策略。
遵循本地优先与跨平台规范，确保数据文件安全存储于操作系统标准用户目录。
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, List
from platformdirs import user_data_dir, user_cache_dir, user_log_dir
from pydantic import BaseModel, Field

APP_NAME = "StockAI"
APP_AUTHOR = "StockAI_Team"
APP_VERSION = "1.0.0"

class LLMProviderConfig(BaseModel):
    """大模型服务商配置实体"""
    name: str = Field(description="服务商显示名称")
    provider_type: str = Field(default="openai", description="协议类型，默认兼容 OpenAI 规范")
    base_url: str = Field(description="API 基础接入地址")
    model_name: str = Field(description="默认调用的模型标识")
    api_key: str = Field(default="", description="用户配置的 API Key")
    temperature: float = Field(default=0.3, description="采样温度，股票分析倾向客观严谨")
    max_tokens: int = Field(default=2000, description="单次最大生成 Token 数")

class AppConfig:
    """应用程序核心全局单例配置管理"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppConfig, cls).__new__(cls)
            cls._instance._init_paths()
            cls._instance._init_defaults()
            cls._instance._setup_logging()
        return cls._instance

    def _init_paths(self):
        """初始化跨平台路径，自动建立所需目录"""
        # 数据根目录
        self.data_dir = Path(user_data_dir(appname=APP_NAME, appauthor=APP_AUTHOR))
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 缓存目录
        self.cache_dir = Path(user_cache_dir(appname=APP_NAME, appauthor=APP_AUTHOR))
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 日志目录
        self.log_dir = Path(user_log_dir(appname=APP_NAME, appauthor=APP_AUTHOR))
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 数据库与配置文件路径
        self.db_path = self.data_dir / "stock_ai.db"
        self.config_json_path = self.data_dir / "settings.json"
        self.log_file_path = self.log_dir / "stock_ai.log"

    def _init_defaults(self):
        """初始化默认参数配置"""
        # 预设大模型提供商
        self.default_providers: Dict[str, LLMProviderConfig] = {
            "DeepSeek": LLMProviderConfig(
                name="DeepSeek",
                base_url="https://api.deepseek.com/v1",
                model_name="deepseek-chat",
            ),
            "Qwen (通义千问)": LLMProviderConfig(
                name="Qwen (通义千问)",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                model_name="qwen-plus",
            ),
            "Kimi (Moonshot)": LLMProviderConfig(
                name="Kimi (Moonshot)",
                base_url="https://api.moonshot.cn/v1",
                model_name="moonshot-v1-8k",
            ),
            "Zhipu (智谱 GLM)": LLMProviderConfig(
                name="Zhipu (智谱 GLM)",
                base_url="https://open.bigmodel.cn/api/paas/v4",
                model_name="glm-4-flash",
            ),
            "Ollama (本地模型)": LLMProviderConfig(
                name="Ollama (本地模型)",
                base_url="http://localhost:11434/v1",
                model_name="qwen2.5:7b",
            ),
            "OpenAI 兼容自定义": LLMProviderConfig(
                name="OpenAI 兼容自定义",
                base_url="https://api.openai.com/v1",
                model_name="gpt-4o-mini",
            ),
        }
        self.current_provider_name = "DeepSeek"
        self.cache_expiry_hours = 4  # 日线/基础行情缓存过期时长（小时）
        self.request_timeout_seconds = 10  # 数据网络请求超时时长（秒）
        self.max_retry_times = 3  # 网络失败最大重试次数

    def _setup_logging(self):
        """配置应用程序全局日志记录"""
        logger = logging.getLogger("StockAI")
        logger.setLevel(logging.INFO)
        logger.propagate = False

        if not logger.handlers:
            # 文件日志
            file_handler = logging.FileHandler(self.log_file_path, encoding="utf-8")
            file_formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s"
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

            # 控制台输出
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)

        self.logger = logger
        self.logger.info("StockAI 全局配置初始化完成。数据存储路径: %s", self.data_dir)

# 全局配置单例导出
config = AppConfig()
logger = config.logger
