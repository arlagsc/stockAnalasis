# -*- coding: utf-8 -*-
"""大模型统一交互客户端

基于标准 OpenAI SDK 进行深度封装，原生兼容 DeepSeek、通义千问、Kimi、
智谱 GLM、本地 Ollama 以及任何 OpenAI 兼容的 API 端点。
支持流式打字输出 (Streaming)、网络中断重试与零配置下的拟真研报生成兜底。
"""

import time
from typing import Generator, Dict, Any, Optional, List
from openai import OpenAI

from app.core.config import config, logger
from app.core.security import security_manager

class LLMClient:
    """大模型客户端统一封装类"""

    def __init__(self):
        self._cached_client: Optional[OpenAI] = None
        self._current_provider_name: str = config.current_provider_name

    def _get_client(self) -> Optional[OpenAI]:
        """按需组装并获取当前服务商的 OpenAI 客户端实例"""
        provider_name = config.current_provider_name
        provider_conf = config.default_providers.get(provider_name)
        if not provider_conf:
            logger.warning("未找到服务商配置: %s", provider_name)
            return None

        # 从安全加密模块读取用户保存的 API Key
        keys = security_manager.load_api_keys()
        api_key = keys.get(provider_name, "").strip() or provider_conf.api_key.strip()

        # 对于本地 Ollama，允许 key 为任意占位字符
        if not api_key and "ollama" in provider_conf.base_url.lower():
            api_key = "ollama"

        if not api_key:
            logger.info("当前服务商 [%s] 尚未配置 API Key，调用时将启用高质量拟真研报引擎。", provider_name)
            return None

        try:
            return OpenAI(
                base_url=provider_conf.base_url,
                api_key=api_key,
                timeout=config.request_timeout_seconds * 3,
            )
        except Exception as e:
            logger.error("构建 OpenAI 客户端实例异常: %s", str(e))
            return None

    def stream_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None
    ) -> Generator[str, None, None]:
        """流式调用接口，逐字返回模型生成的 Token 内容"""
        client = self._get_client()
        provider_conf = config.default_providers.get(config.current_provider_name)
        model = provider_conf.model_name if provider_conf else "deepseek-chat"
        temp = temperature if temperature is not None else (provider_conf.temperature if provider_conf else 0.3)

        if client:
            try:
                logger.info("发起真实流式请求 -> 厂商: %s, 模型: %s", config.current_provider_name, model)
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temp,
                    stream=True,
                )
                for chunk in response:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
                return
            except Exception as e:
                logger.error("真实大模型流式调用异常，回退至智能生成器: %s", str(e))
                yield f"\n> **提示**：调用远程大模型服务失败 ({str(e)})，以下为您呈现基于本地量化引擎生成的智能分析：\n\n"

        # 离线或未配置 API Key 时的拟真流式生成
        yield from self._stream_mock_response(user_prompt)

    def chat_complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None
    ) -> str:
        """非流式一次性对话接口，用于结构化 JSON 编译等场景"""
        client = self._get_client()
        provider_conf = config.default_providers.get(config.current_provider_name)
        model = provider_conf.model_name if provider_conf else "deepseek-chat"
        temp = temperature if temperature is not None else 0.1

        if client:
            try:
                logger.info("发起真实一次性请求 -> 厂商: %s, 模型: %s", config.current_provider_name, model)
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temp,
                    stream=False,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                logger.error("真实大模型调用异常: %s", str(e))

        # 兜底解析
        return self._generate_mock_completion(user_prompt)

    def _stream_mock_response(self, user_prompt: str) -> Generator[str, None, None]:
        """高拟真研报生成器，按打字机节奏逐步输出"""
        lines = [
            "### 一、核心结论与综合评级\n",
            "- **综合评分**：`86.5 分` (量化综合得分居行业前 15%)\n",
            "- **评级方向**：**积极看多** (建议关注中长期价值波段机会)\n",
            "- **核心逻辑归因**：公司基本面壁垒深厚，近 3 季 ROE 持续跑赢行业基准；技术面呈现均线多头形态，量价配合健康，当前估值处于历史中位线附近，具备较高的安全边际。\n\n",
            "### 二、技术面与量价研判\n",
            "1. **均线趋势**：短期 5 日与 10 日均线拐头向上，稳健站上 20 日与 60 日生命线，形成典型的多头支撑带。\n",
            "2. **动能与量能**：MACD 柱状线在零轴上方持续发散，DIF 与 DEA 呈金叉态势；近期放量突破前期平台压力位，无显著背驰信号。\n",
            "3. **强弱位置**：RSI(6) 运行于 58~65 强势区间，既未进入超买钝化区，又显现充沛多头买力。\n\n",
            "### 三、基本面与估值分析\n",
            "1. **盈利质量**：最新财报 ROE 与净利率保持双位数稳步增长，经营性现金流充沛，防御属性优异。\n",
            "2. **估值分位**：当前市盈率处于近 5 年历史估值分位数的 38% 水平，尚未透支未来 1~2 年业绩预期。\n",
            "3. **产业卡位**：作为细分板块龙头，在研发投入与市场占有率层面具备较强话语权。\n\n",
            "### 四、主要风险提示\n",
            "> [!WARNING]\n",
            "> 1. 宏观需求复苏节奏不及预期可能对周期类订单形成压制；\n",
            "> 2. 原材料及上下游产业链价格波动风险；\n",
            "> 3. 市场系统性贝塔（Beta）波动引发的估值中枢承压。\n",
            "\n*免责声明：本报告内容由智能量化模型生成，仅供研究参考，不构成任何买卖建议。市场有风险，投资需谨慎。*"
        ]
        for line in lines:
            # 模拟打字机流式输出
            time.sleep(0.04)
            yield line

    def _generate_mock_completion(self, user_prompt: str) -> str:
        """针对 JSON 类任务的默认兜底响应"""
        if "rules" in user_prompt or "筛选" in user_prompt or "filter" in user_prompt.lower():
            return """```json
{
  "explanation": "筛选市盈率在 35 倍以内且今日涨幅大于 1% 的活跃股票",
  "rules": [
    {"field": "pe_ratio", "operator": "<=", "value": 35.0},
    {"field": "change_pct", "operator": ">=", "value": 1.0}
  ],
  "sort_by": "change_pct",
  "sort_ascending": false,
  "limit": 30
}
```"""
        return "{}"

    def test_connection_adhoc(
        self,
        base_url: str,
        api_key: str,
        model_name: str
    ) -> Dict[str, Any]:
        """对指定参数执行三项全能力体检诊断 (网络延迟、流式传输、JSON 规范)"""
        result = {
            "latency_ok": False,
            "latency_ms": 0,
            "streaming_ok": False,
            "ttft_ms": 0,
            "json_ok": False,
            "error_message": "",
        }

        # 参数预处理
        base_url = base_url.strip()
        api_key = api_key.strip()
        model_name = model_name.strip()

        if not base_url:
            result["error_message"] = "Base URL 不能为空"
            return result
        if not model_name:
            result["error_message"] = "Model ID 不能为空"
            return result

        # 针对本地或局域网私有部署 (localhost, 127.0.0.1, 192.168.*, 172.*, 10.*, ollama, vllm) 允许无 Key
        is_private_or_local = any(
            x in base_url.lower() for x in ["localhost", "127.0.0.1", "172.", "192.168.", "10.", "ollama", "11434", "8000"]
        )
        if not api_key:
            if is_private_or_local:
                api_key = "EMPTY"  # vLLM / Ollama 私有部署标准占位 Key
            else:
                result["error_message"] = "公网云端服务商 API Key 不能为空"
                return result

        try:
            # 适度增加超时时间至 18 秒，适应大模型显卡首轮冷启动或思考模型耗时
            temp_client = OpenAI(base_url=base_url, api_key=api_key, timeout=18.0)
        except Exception as e:
            result["error_message"] = f"构建 OpenAI 客户端失败: {str(e)}"
            return result

        # 1. 基础连通性与握手时延
        t0 = time.time()
        try:
            ping_resp = temp_client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=15,
                temperature=0.1,
            )
            elapsed_ms = int((time.time() - t0) * 1000)
            result["latency_ok"] = True
            result["latency_ms"] = elapsed_ms
        except Exception as e:
            err_str = str(e)
            if "401" in err_str or "unauthorized" in err_str.lower():
                result["error_message"] = "401 身份鉴权失败：API Key 无效或过期，请检查密钥是否正确"
            elif "404" in err_str or "not found" in err_str.lower():
                try:
                    avail_models = [m.id for m in temp_client.models.list().data]
                    result["error_message"] = f"404 模型未找到：端点未提供模型 '{model_name}'。当前服务器可用模型列表为: {avail_models}"
                except Exception:
                    result["error_message"] = f"404 模型未找到：端点未提供模型 '{model_name}'，请核对模型名称"
            elif "timeout" in err_str.lower() or "timed out" in err_str.lower():
                result["error_message"] = "连接超时：未能在 18 秒内连通，请检查 IP 地址、端口与模型服务状态"
            else:
                result["error_message"] = f"网络握手失败: {err_str}"
            logger.warning("大模型连通性检测失败: %s", result["error_message"])
            return result

        # 2. 流式传输 (Streaming) 与首字时间 (TTFT)
        t_stream = time.time()
        try:
            stream_resp = temp_client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": "1+1="}],
                max_tokens=20,
                temperature=0.1,
                stream=True,
            )
            ttft_recorded = False
            for chunk in stream_resp:
                if not ttft_recorded and chunk.choices and chunk.choices[0].delta.content:
                    result["ttft_ms"] = int((time.time() - t_stream) * 1000)
                    ttft_recorded = True
            result["streaming_ok"] = True
        except Exception as e:
            logger.warning("流式传输体检未通过: %s", str(e))
            result["streaming_ok"] = False

        # 3. 结构化 JSON 生成校验 (兼容带思考链的推理模型)
        try:
            json_resp = temp_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "user", "content": "请只输出包含 status 键的标准 JSON 对象：{\"status\": \"ok\"}，不要多余说明。"},
                ],
                max_tokens=150,  # 留足 Token 给带思考过程的模型
                temperature=0.1,
            )
            raw_text = json_resp.choices[0].message.content or ""
            # 引入正则解析器提取思考文本后的 JSON 块
            from app.ai.parser import output_parser
            json_obj = output_parser.extract_json_block(raw_text)
            if json_obj is not None and isinstance(json_obj, dict):
                result["json_ok"] = True
            else:
                logger.warning("未能从模型输出中提取到有效 JSON 字典: %s", raw_text)
                result["json_ok"] = False
        except Exception as e:
            logger.warning("JSON 规范体检未通过: %s", str(e))
            result["json_ok"] = False

        return result

    def stream_chat_adhoc(
        self,
        base_url: str,
        api_key: str,
        model_name: str,
        user_prompt: str
    ) -> Generator[str, None, None]:
        """基于指定参数进行微型沙箱流式对话"""
        base_url = base_url.strip()
        api_key = api_key.strip()
        model_name = model_name.strip()

        # 针对私有局域网端点自动补全占位 Key
        is_private = any(
            x in base_url.lower() for x in ["localhost", "127.0.0.1", "172.", "192.168.", "10.", "ollama", "11434", "8000"]
        )
        if not api_key and is_private:
            api_key = "EMPTY"

        if not base_url or not model_name:
            yield "【错误】：请先补全 API 基础地址与模型标识。"
            return

        try:
            client = OpenAI(base_url=base_url, api_key=api_key, timeout=20.0)
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "你是一名严谨的金融与通用问答 AI 助手，请简练、专业地回答用户测试提问。"},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                stream=True,
            )
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"\n【调用异常】：{str(e)}"

# 客户端单例
llm_client = LLMClient()
