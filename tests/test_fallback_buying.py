# -*- coding: utf-8 -*-
"""测试大模型故障/超时场景下本地多因子兜底建仓全链路"""

import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.trading_service import trading_service
from app.services.auto_trader import auto_trader
from app.ai.llm_client import llm_client

def test_fallback_buying_on_llm_timeout():
    print("==================================================")
    print(">>> 测试：模拟大模型超时异常，验证本地量化兜底建仓 <<<")
    print("==================================================")

    # 1. 重置 AI 账户资金为 100,000 元
    trading_service.reset_account("AI", initial_capital=100000.0)
    print("[1] 账户资金已重置为 100,000 元")

    # 2. Mock llm_client.chat_complete 模拟抛出 Request timed out 异常或返回空
    with patch.object(llm_client, "chat_complete", side_effect=Exception("Request timed out.")):
        res = auto_trader.execute_auto_trading(account_type="AI", max_buy_count=2)

    print(f"[2] 执行建仓结果: success={res['success']}, msg={res['msg']}, executed_count={res['executed_count']}")
    
    # 3. 断言验证
    assert res["success"] is True, f"兜底建仓应该成功，但返回了失败: {res['msg']}"
    assert res["executed_count"] >= 1, f"应该买入至少 1 支标的，实际买入 {res['executed_count']} 支"
    assert len(res["bought_items"]) == res["executed_count"]

    # 4. 验证持仓与流水
    positions = trading_service.get_positions("AI")
    print(f"[3] 成功建仓 {len(positions)} 支持仓:")
    for pos in positions:
        print(f"    - [{pos['symbol']} {pos['name']}] 买入持仓: {pos['total_amount']} 股, 现价: {pos['current_price']} 元, 成本: {pos['cost_price']} 元")
        assert pos["available_amount"] == 0, "T+1 锁定状态必须为 0 股可用"

    print("==================================================")
    print(">>> 验证通过！本地多因子兜底建仓引擎运行正常！<<<")
    print("==================================================")

if __name__ == "__main__":
    test_fallback_buying_on_llm_timeout()
