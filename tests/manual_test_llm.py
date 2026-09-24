# -*- coding: utf-8 -*-
"""手动触发当前大模型服务进行全方位连通性与实战建仓推理测试"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import config
from app.core.security import security_manager
from app.ai.llm_client import llm_client
from app.ai.prompts import AUTO_TRADE_SYSTEM_PROMPT, AUTO_TRADE_USER_TEMPLATE

def test_llm():
    provider_name = config.current_provider_name
    conf = config.default_providers.get(provider_name)
    keys = security_manager.load_api_keys()
    api_key = keys.get(provider_name, "").strip() or conf.api_key.strip()

    print("==================================================")
    print(">>> 1. 检查大模型配置参数 <<<")
    print(f"厂商名称: {provider_name}")
    print(f"Base URL: {conf.base_url}")
    print(f"模型名称: {conf.model_name}")
    print(f"API Key 配置状态: {'已配置 (长度 ' + str(len(api_key)) + ')' if api_key else '未配置'}")
    print("==================================================")

    # 1. 诊断网络与三项能力体检
    print("\n>>> 2. 执行三项全能力体检诊断 (延迟 / 流式传输 / JSON 解析) <<<")
    start_diag = time.time()
    diag_res = llm_client.test_connection_adhoc(
        base_url=conf.base_url,
        api_key=api_key,
        model_name=conf.model_name
    )
    cost_diag = time.time() - start_diag
    print(f"诊断总耗时: {cost_diag:.2f} 秒")
    print(f"网络与首字响应 (Latency OK): {diag_res['latency_ok']}, 耗时: {diag_res['latency_ms']} ms")
    print(f"流式传输 (Streaming OK): {diag_res['streaming_ok']}, 首字用时 (TTFT): {diag_res['ttft_ms']} ms")
    print(f"JSON 结构化规范 (JSON OK): {diag_res['json_ok']}")
    if diag_res.get("error_message"):
        print(f"异常信息: {diag_res['error_message']}")

    # 2. 真实场景模拟：发送建仓决策 Prompt（完全模拟实战 09:35 建仓）
    print("\n>>> 3. 发送实战建仓决策 Prompt 测试真实大模型一次性推理 <<<")
    candidates_text = (
        "1. [标的A(600001)] 现价: 12.50元, 今日涨幅: +3.20%, 换手率: 4.50%, PE: 15.2, 初筛评分: 85.0\n"
        "2. [标的B(000002)] 现价: 8.80元, 今日涨幅: +2.10%, 换手率: 3.20%, PE: 11.5, 初筛评分: 82.0\n"
        "3. [标的C(300033)] 现价: 45.60元, 今日涨幅: +4.80%, 换手率: 6.80%, PE: 32.1, 初筛评分: 88.0"
    )
    skills_text = "【系统操盘军规】：优先选择量价齐升、均线向上发散的突破形态标的，坚决规避高位滞涨标的。"
    user_prompt = AUTO_TRADE_USER_TEMPLATE.format(
        skills_block=skills_text,
        candidates_block=candidates_text
    )

    t0 = time.time()
    try:
        response_text = llm_client.chat_complete(
            system_prompt=AUTO_TRADE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.2
        )
        total_time = time.time() - t0
        print(f"\n[真实大模型调用成功] 总响应耗时: {total_time:.2f} 秒")
        print("模型原始返回内容:\n----------------------------------------")
        print(response_text)
        print("----------------------------------------")
    except Exception as e:
        total_time = time.time() - t0
        print(f"\n[大模型调用异常] 耗时 {total_time:.2f} 秒: {str(e)}")

if __name__ == "__main__":
    test_llm()
