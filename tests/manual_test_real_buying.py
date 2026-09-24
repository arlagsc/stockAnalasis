# -*- coding: utf-8 -*-
"""手动触发一次真实的 AI 一键建仓管线（真实大模型裁决）"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.trading_service import trading_service
from app.services.auto_trader import auto_trader

def main():
    print("==================================================")
    print(">>> 手动触发真实 AI 一键建仓管线 (直连 qwen3.8-vllm) <<<")
    print("==================================================")

    # 1. 确保账户资金充沛
    trading_service.reset_account("AI", initial_capital=100000.0)

    # 2. 驱动真实建仓管线
    res = auto_trader.execute_auto_trading(account_type="AI", max_buy_count=2)

    print(f"\n建仓结果: success={res['success']}, msg={res['msg']}, executed_count={res['executed_count']}")
    if res.get("bought_items"):
        print("成功买入标的:")
        for item in res["bought_items"]:
            print(f"  - [{item['symbol']} {item['name']}] 买入: {item['amount']} 股, 成交价: {item['price']} 元, 成交额: {item['total_value']} 元, 决策理由: {item['reason']}")

    positions = trading_service.get_positions("AI")
    print(f"\n当前持仓总数: {len(positions)} 支")
    for p in positions:
        print(f"  - {p['name']}({p['symbol']}): 总持股 {p['total_amount']}, 可用 {p['available_amount']} (T+1锁定), 市值 {p['market_value']} 元")

if __name__ == "__main__":
    main()
