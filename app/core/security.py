# -*- coding: utf-8 -*-
"""凭据安全与加密模块

负责本地敏感信息（如各大模型厂商 API Key）的安全存储与加解密。
提供基于本地保护密钥的加解密实现，避免明文落盘。
"""

import os
import json
import base64
from pathlib import Path
from typing import Dict, Optional
from cryptography.fernet import Fernet
from app.core.config import config, logger

class SecurityManager:
    """本地安全凭据管理器"""

    def __init__(self):
        self._key_file = config.data_dir / ".secret.key"
        self._fernet = self._init_fernet()

    def _init_fernet(self) -> Fernet:
        """初始化或加载本地加密密钥"""
        try:
            if self._key_file.exists():
                with open(self._key_file, "rb") as f:
                    key = f.read().strip()
            else:
                key = Fernet.generate_key()
                with open(self._key_file, "wb") as f:
                    f.write(key)
                logger.info("已生成新的本地安全密钥文件。")
            return Fernet(key)
        except Exception as e:
            logger.error("初始化安全密钥失败，使用临时内存密钥: %s", str(e))
            return Fernet(Fernet.generate_key())

    def encrypt_text(self, plain_text: str) -> str:
        """加密文本内容为 Base64 字符串"""
        if not plain_text:
            return ""
        try:
            encrypted_bytes = self._fernet.encrypt(plain_text.encode("utf-8"))
            return base64.b64encode(encrypted_bytes).decode("utf-8")
        except Exception as e:
            logger.error("文本加密异常: %s", str(e))
            return ""

    def decrypt_text(self, encrypted_b64: str) -> str:
        """解密 Base64 密文字符串"""
        if not encrypted_b64:
            return ""
        try:
            encrypted_bytes = base64.b64decode(encrypted_b64.encode("utf-8"))
            decrypted_bytes = self._fernet.decrypt(encrypted_bytes)
            return decrypted_bytes.decode("utf-8")
        except Exception as e:
            logger.error("文本解密异常: %s", str(e))
            return ""

    def save_api_keys(self, provider_keys: Dict[str, str]):
        """安全持久化保存各服务商的 API Key"""
        encrypted_dict = {}
        for provider, key in provider_keys.items():
            if key:
                encrypted_dict[provider] = self.encrypt_text(key)

        save_path = config.data_dir / "credentials.enc"
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(encrypted_dict, f, ensure_ascii=False, indent=2)
            logger.info("已成功保存加密的 API Key 凭据。")
        except Exception as e:
            logger.error("保存凭据文件失败: %s", str(e))

    def load_api_keys(self) -> Dict[str, str]:
        """读取并解密所有服务商的 API Key"""
        load_path = config.data_dir / "credentials.enc"
        if not load_path.exists():
            return {}

        result = {}
        try:
            with open(load_path, "r", encoding="utf-8") as f:
                encrypted_dict = json.load(f)
            for provider, enc_val in encrypted_dict.items():
                result[provider] = self.decrypt_text(enc_val)
            logger.info("已成功读取并解密本地 API Key 凭据，包含服务商数量: %d", len(result))
        except Exception as e:
            logger.error("读取凭据文件失败: %s", str(e))
        return result

# 全局安全管理器实例
security_manager = SecurityManager()
