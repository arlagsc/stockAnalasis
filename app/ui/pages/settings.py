# -*- coding: utf-8 -*-
"""系统设置与大模型参数配置页面

提供大模型厂商切换、API Key 安全加密保存、
全能力异步体检诊断 (网络握手/流式Streaming/JSON)、
交互式即时问答沙箱测试、数据缓存维护及合规免责声明展示。
"""

import time
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QFrame, QMessageBox, QTextEdit, QScrollArea
)
from PySide6.QtCore import Qt, QThread, Signal

from app.core.config import config, logger
from app.core.security import security_manager
from app.data.cache_manager import cache_manager
from app.ai.llm_client import llm_client

class LLMTestWorker(QThread):
    """大模型全能力体检诊断后台工作线程"""

    finished_signal = Signal(dict)

    def __init__(self, base_url: str, api_key: str, model_name: str):
        super().__init__()
        self.base_url = base_url
        self.api_key = api_key
        self.model_name = model_name

    def run(self):
        result = llm_client.test_connection_adhoc(
            base_url=self.base_url,
            api_key=self.api_key,
            model_name=self.model_name,
        )
        self.finished_signal.emit(result)

class LLMSandboxWorker(QThread):
    """交互式沙箱流式对话后台工作线程"""

    chunk_received = Signal(str)
    finished_signal = Signal(str)

    def __init__(self, base_url: str, api_key: str, model_name: str, prompt: str):
        super().__init__()
        self.base_url = base_url
        self.api_key = api_key
        self.model_name = model_name
        self.prompt = prompt
        self.full_response = ""

    def run(self):
        try:
            for chunk in llm_client.stream_chat_adhoc(
                base_url=self.base_url,
                api_key=self.api_key,
                model_name=self.model_name,
                user_prompt=self.prompt,
            ):
                self.full_response += chunk
                self.chunk_received.emit(chunk)
            self.finished_signal.emit(self.full_response)
        except Exception as e:
            err = f"\n测试交互异常: {str(e)}"
            self.full_response += err
            self.chunk_received.emit(err)
            self.finished_signal.emit(self.full_response)

class SettingsPage(QWidget):
    """系统配置、API 凭据管理与大模型测试套件页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._test_worker: Optional[LLMTestWorker] = None
        self._sandbox_worker: Optional[LLMSandboxWorker] = None
        self._init_ui()

    def _init_ui(self):
        # 整体滚动区域以容纳测试套件
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)

        # 1. 顶部标题
        title_box = QVBoxLayout()
        lbl_title = QLabel("系统设置与模型接入")
        lbl_title.setObjectName("TitleLabel")
        lbl_sub = QLabel("配置大模型接入凭据、运行全能力体检诊断与即时问答测试")
        lbl_sub.setObjectName("SubTitleLabel")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        layout.addLayout(title_box)

        # 2. 大模型配置卡片
        llm_card = QFrame()
        llm_card.setObjectName("CardPanel")
        llm_layout = QVBoxLayout(llm_card)
        llm_layout.setContentsMargins(18, 16, 18, 16)
        llm_layout.setSpacing(12)

        lbl_llm_head = QLabel("大语言模型接入配置 (BYOK 自带 Key 模式)")
        lbl_llm_head.setStyleSheet("font-size: 15px; font-weight: bold; color: #38BDF8;")
        llm_layout.addWidget(lbl_llm_head)

        # 选择厂商
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("选择服务商:"))
        self.combo_provider = QComboBox()
        self.combo_provider.addItems(list(config.default_providers.keys()))
        self.combo_provider.currentTextChanged.connect(self._on_provider_changed)
        row1.addWidget(self.combo_provider)
        row1.addStretch()
        llm_layout.addLayout(row1)

        # API 基础地址
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("API 基础地址 (Base URL):"))
        self.input_base_url = QLineEdit()
        row2.addWidget(self.input_base_url)
        llm_layout.addLayout(row2)

        # 默认模型名称
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("调用模型名称 (Model ID):"))
        self.input_model_name = QLineEdit()
        row3.addWidget(self.input_model_name)
        
        self.btn_fetch_models = QPushButton("自动拉取端点模型")
        self.btn_fetch_models.setObjectName("SecondaryButton")
        self.btn_fetch_models.clicked.connect(self._on_fetch_models_clicked)
        row3.addWidget(self.btn_fetch_models)
        llm_layout.addLayout(row3)

        # API Key
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("API Key 密钥凭据:"))
        self.input_api_key = QLineEdit()
        self.input_api_key.setEchoMode(QLineEdit.Password)
        self.input_api_key.setPlaceholderText("请输入该服务商的 API Key (本地 AES 加密安全保存)")
        row4.addWidget(self.input_api_key)
        llm_layout.addLayout(row4)

        # 操作按钮行：一键全能体检 + 安全保存
        btn_row = QHBoxLayout()
        self.btn_test_llm = QPushButton("一键全能力体检诊断")
        self.btn_test_llm.setObjectName("SecondaryButton")
        self.btn_test_llm.clicked.connect(self._on_run_diagnostic_clicked)
        btn_row.addWidget(self.btn_test_llm)

        self.btn_save_llm = QPushButton("安全保存模型配置")
        self.btn_save_llm.clicked.connect(self._on_save_llm_clicked)
        btn_row.addWidget(self.btn_save_llm)
        btn_row.addStretch()
        llm_layout.addLayout(btn_row)

        # 3. 体检状态徽章显示栏
        self.diag_panel = QFrame()
        self.diag_panel.setStyleSheet("background: #15181F; border: 1px dashed #2B313D; border-radius: 6px; padding: 6px;")
        diag_layout = QVBoxLayout(self.diag_panel)
        diag_layout.setContentsMargins(10, 8, 10, 8)
        diag_layout.setSpacing(6)

        diag_badges = QHBoxLayout()
        self.lbl_diag_ping = QLabel("网络握手: 待测试")
        self.lbl_diag_ping.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 500;")
        
        self.lbl_diag_stream = QLabel("流式传输: 待测试")
        self.lbl_diag_stream.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 500;")

        self.lbl_diag_json = QLabel("JSON 格式支持: 待测试")
        self.lbl_diag_json.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 500;")

        diag_badges.addWidget(self.lbl_diag_ping)
        diag_badges.addWidget(self.lbl_diag_stream)
        diag_badges.addWidget(self.lbl_diag_json)
        diag_badges.addStretch()
        diag_layout.addLayout(diag_badges)

        self.lbl_diag_detail = QLabel("点击【一键全能力体检诊断】按钮，即可校验上述参数的连通性与模型输出能力。")
        self.lbl_diag_detail.setStyleSheet("color: #64748B; font-size: 11px;")
        self.lbl_diag_detail.setWordWrap(True)
        diag_layout.addWidget(self.lbl_diag_detail)
        llm_layout.addWidget(self.diag_panel)

        # 4. 交互式微型测试问答控制台 (Sandbox)
        sandbox_card = QFrame()
        sandbox_card.setStyleSheet("background: #181B22; border: 1px solid #282D38; border-radius: 6px; padding: 8px;")
        sb_layout = QVBoxLayout(sandbox_card)
        sb_layout.setContentsMargins(10, 8, 10, 8)
        sb_layout.setSpacing(8)

        lbl_sb_head = QLabel("即时问答测试沙箱 (Sandbox Console)")
        lbl_sb_head.setStyleSheet("color: #E2E8F0; font-size: 12px; font-weight: bold;")
        sb_layout.addWidget(lbl_sb_head)

        sb_input_box = QHBoxLayout()
        self.input_sb_prompt = QLineEdit()
        self.input_sb_prompt.setText("请用一句话介绍你的量化金融分析能力。")
        self.btn_send_test = QPushButton("发送测试")
        self.btn_send_test.clicked.connect(self._on_send_sandbox_test)
        sb_input_box.addWidget(self.input_sb_prompt)
        sb_input_box.addWidget(self.btn_send_test)
        sb_layout.addLayout(sb_input_box)

        self.txt_sb_response = QTextEdit()
        self.txt_sb_response.setReadOnly(True)
        self.txt_sb_response.setFixedHeight(80)
        self.txt_sb_response.setPlaceholderText("测试问答实时流式打字结果将在此显示...")
        sb_layout.addWidget(self.txt_sb_response)
        llm_layout.addWidget(sandbox_card)

        layout.addWidget(llm_card)

        # 5. 本地数据与缓存管理卡片
        data_card = QFrame()
        data_card.setObjectName("CardPanel")
        data_layout = QVBoxLayout(data_card)
        data_layout.setContentsMargins(18, 16, 18, 16)
        data_layout.setSpacing(10)

        lbl_data_head = QLabel("本地数据库与缓存维护")
        lbl_data_head.setStyleSheet("font-size: 15px; font-weight: bold; color: #F8FAFC;")
        data_layout.addWidget(lbl_data_head)

        lbl_path = QLabel(f"本地持久化数据存储路径: {config.data_dir}")
        lbl_path.setStyleSheet("color: #94A3B8; font-size: 12px;")
        data_layout.addWidget(lbl_path)

        data_btn_box = QHBoxLayout()
        btn_sync = QPushButton("强制全量同步最新 A 股数据")
        btn_sync.clicked.connect(self._on_force_sync)
        data_btn_box.addWidget(btn_sync)
        data_btn_box.addStretch()
        data_layout.addLayout(data_btn_box)
        layout.addWidget(data_card)

        # 6. 法律合规与免责声明卡片
        disclaimer_card = QFrame()
        disclaimer_card.setObjectName("CardPanel")
        dis_layout = QVBoxLayout(disclaimer_card)
        dis_layout.setContentsMargins(18, 14, 18, 14)
        
        lbl_dis_title = QLabel("投资风险与法律合规免责声明")
        lbl_dis_title.setStyleSheet("font-weight: bold; color: #F59E0B; font-size: 13px;")
        dis_layout.addWidget(lbl_dis_title)

        lbl_dis_text = QLabel(
            "1. 本软件定位为证券量化分析、学术研讨与个人辅助决策工具，所有输出报告与数据均不构成任何实质性投资建议或买卖依据；\n"
            "2. 证券市场有风险，投资需独立审慎判断。对于依据本软件数据进行自主交易所导致的任何直接或间接损益，开发者不承担任何责任；\n"
            "3. 所有数据来自公开网络及 AkShare 开源接口，请在合规范围内研究使用。"
        )
        lbl_dis_text.setStyleSheet("color: #94A3B8; font-size: 11px; line-height: 1.5;")
        dis_layout.addWidget(lbl_dis_text)
        layout.addWidget(disclaimer_card)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        # 加载初始数据
        self._load_current_provider_settings()

    def _load_current_provider_settings(self):
        """填充当前服务商的配置信息"""
        provider_name = self.combo_provider.currentText()
        provider_conf = config.default_providers.get(provider_name)
        if provider_conf:
            self.input_base_url.setText(provider_conf.base_url)
            self.input_model_name.setText(provider_conf.model_name)
            
            # 读取已保存的 Key
            keys = security_manager.load_api_keys()
            self.input_api_key.setText(keys.get(provider_name, ""))

    def _on_provider_changed(self, text: str):
        config.current_provider_name = text
        self._load_current_provider_settings()
        self._reset_diagnostic_ui()

    def _reset_diagnostic_ui(self):
        """重置体检状态徽章"""
        self.lbl_diag_ping.setText("网络握手: 待测试")
        self.lbl_diag_ping.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 500;")
        self.lbl_diag_stream.setText("流式传输: 待测试")
        self.lbl_diag_stream.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 500;")
        self.lbl_diag_json.setText("JSON 格式支持: 待测试")
        self.lbl_diag_json.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 500;")
        self.lbl_diag_detail.setText("参数已切换，点击【一键全能力体检诊断】进行测试。")
        self.lbl_diag_detail.setStyleSheet("color: #64748B; font-size: 11px;")
        self.txt_sb_response.clear()

    def _on_run_diagnostic_clicked(self):
        """启动后台全能力体检"""
        base_url = self.input_base_url.text().strip()
        model_name = self.input_model_name.text().strip()
        api_key = self.input_api_key.text().strip()

        if not base_url or not model_name:
            QMessageBox.warning(self, "提示", "请先输入 API 基础地址 (Base URL) 与模型标识 (Model ID)。")
            return

        self.btn_test_llm.setEnabled(False)
        self.btn_test_llm.setText("正在执行体检...")
        self.lbl_diag_detail.setText("正在发起网络握手、流式通道与结构化输出能力体检...")
        self.lbl_diag_detail.setStyleSheet("color: #38BDF8; font-size: 11px;")

        # 启动工作线程
        self._test_worker = LLMTestWorker(base_url, api_key, model_name)
        self._test_worker.finished_signal.connect(self._on_diagnostic_finished)
        self._test_worker.start()

    def _on_diagnostic_finished(self, res: Dict[str, Any]):
        """体检完成回调并刷新界面指示器"""
        self.btn_test_llm.setEnabled(True)
        self.btn_test_llm.setText("一键全能力体检诊断")

        # 1. 握手结果
        if res.get("latency_ok"):
            ms = res.get("latency_ms", 0)
            self.lbl_diag_ping.setText(f"网络握手: 正常 ({ms} ms)")
            self.lbl_diag_ping.setStyleSheet("color: #10B981; font-size: 12px; font-weight: bold;")
        else:
            self.lbl_diag_ping.setText("网络握手: 失败")
            self.lbl_diag_ping.setStyleSheet("color: #EF4444; font-size: 12px; font-weight: bold;")

        # 2. 流式结果
        if res.get("streaming_ok"):
            ttft = res.get("ttft_ms", 0)
            self.lbl_diag_stream.setText(f"流式传输: 支持 (首字 {ttft} ms)")
            self.lbl_diag_stream.setStyleSheet("color: #10B981; font-size: 12px; font-weight: bold;")
        else:
            self.lbl_diag_stream.setText("流式传输: 异常或受限")
            self.lbl_diag_stream.setStyleSheet("color: #F59E0B; font-size: 12px; font-weight: bold;")

        # 3. JSON 结果
        if res.get("json_ok"):
            self.lbl_diag_json.setText("JSON 格式支持: 正常")
            self.lbl_diag_json.setStyleSheet("color: #10B981; font-size: 12px; font-weight: bold;")
        else:
            self.lbl_diag_json.setText("JSON 格式支持: 异常")
            self.lbl_diag_json.setStyleSheet("color: #F59E0B; font-size: 12px; font-weight: bold;")

        # 详细错误或成功汇总
        err = res.get("error_message")
        if err:
            self.lbl_diag_detail.setText(f"体检未通过：{err}")
            self.lbl_diag_detail.setStyleSheet("color: #EF4444; font-size: 11px;")
        else:
            self.lbl_diag_detail.setText("体检全部通过！该大模型端点已具备完整接入条件，可点击【安全保存模型配置】。")
            self.lbl_diag_detail.setStyleSheet("color: #10B981; font-size: 11px; font-weight: 500;")

    def _on_send_sandbox_test(self):
        """发送测试提问至微型沙箱"""
        prompt = self.input_sb_prompt.text().strip()
        if not prompt:
            return
        base_url = self.input_base_url.text().strip()
        model_name = self.input_model_name.text().strip()
        api_key = self.input_api_key.text().strip()

        self.btn_send_test.setEnabled(False)
        self.btn_send_test.setText("正在回复...")
        self.txt_sb_response.clear()

        self._sandbox_worker = LLMSandboxWorker(base_url, api_key, model_name, prompt)
        self._sandbox_worker.chunk_received.connect(self._on_sandbox_chunk)
        self._sandbox_worker.finished_signal.connect(self._on_sandbox_finished)
        self._sandbox_worker.start()

    def _on_sandbox_chunk(self, chunk: str):
        cursor = self.txt_sb_response.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(chunk)
        self.txt_sb_response.setTextCursor(cursor)

    def _on_sandbox_finished(self, full_resp: str):
        self.btn_send_test.setEnabled(True)
        self.btn_send_test.setText("发送测试")

    def _on_save_llm_clicked(self):
        """保存模型配置与加密 API Key"""
        provider = self.combo_provider.currentText()
        key = self.input_api_key.text().strip()
        base_url = self.input_base_url.text().strip()
        model_name = self.input_model_name.text().strip()

        # 更新内存配置
        if provider in config.default_providers:
            config.default_providers[provider].base_url = base_url
            config.default_providers[provider].model_name = model_name

        # 加密保存 Key
        keys = security_manager.load_api_keys()
        keys[provider] = key
        security_manager.save_api_keys(keys)

        QMessageBox.information(self, "保存成功", f"服务商 [{provider}] 的配置与 API Key 已安全加密存储！")

    def _on_fetch_models_clicked(self):
        """自动请求端点 /v1/models 探测可用模型列表并自动填充"""
        base_url = self.input_base_url.text().strip()
        api_key = self.input_api_key.text().strip()
        if not base_url:
            QMessageBox.warning(self, "提示", "请先填写 API 基础地址 (Base URL)。")
            return

        is_private = any(
            x in base_url.lower() for x in ["localhost", "127.0.0.1", "172.", "192.168.", "10.", "ollama", "11434", "8000"]
        )
        if not api_key and is_private:
            api_key = "EMPTY"

        self.btn_fetch_models.setEnabled(False)
        self.btn_fetch_models.setText("正在拉取...")
        try:
            from openai import OpenAI
            client = OpenAI(base_url=base_url, api_key=api_key or "EMPTY", timeout=5.0)
            models = client.models.list()
            model_ids = [m.id for m in models.data]
            if model_ids:
                # 自动填入首个模型
                chosen = model_ids[0]
                self.input_model_name.setText(chosen)
                QMessageBox.information(
                    self, "获取成功",
                    f"成功获取到端点可用模型：\n{', '.join(model_ids)}\n\n已自动为您填入: {chosen}"
                )
            else:
                QMessageBox.warning(self, "提示", "端点已连通，但未返回任何可用模型标识。")
        except Exception as e:
            QMessageBox.warning(self, "拉取失败", f"无法从端点获取模型列表: {str(e)}")
        finally:
            self.btn_fetch_models.setEnabled(True)
            self.btn_fetch_models.setText("自动拉取端点模型")

    def _on_force_sync(self):
        """强制同步全量数据"""
        cache_manager.sync_stocks_from_source()
        QMessageBox.information(self, "成功", "全市场股票数据已重新同步入库！")
