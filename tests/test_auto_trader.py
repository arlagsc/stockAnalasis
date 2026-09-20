# -*- coding: utf-8 -*-
"""AI 自动计算建仓中枢 (AutoTrader) 自动化集成测试

覆盖用例:
1. 风控拦截 (可用现金低于 2000 元门槛拦截)
2. 全流程 AI 自动计算建仓 (多因子向量化初筛 + 操盘军规注入 + 动态分仓 + 100 股撮合)
3. A 股仿真撮合与 T+1 纪律验证 (当日可用股数严格锁定为 0, 流水记录包含决策理由)
4. 防重复建仓机制 (自动剔除已持仓股票)
5. 持仓上限风控拦截 (达到 5 支最大分散上限时安全拦截)
"""

import sys
import os

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import logger
from app.services.trading_service import trading_service
from app.services.auto_trader import auto_trader


def run_tests():
    print("==================================================")
    print(">>> 开始执行 AI 自动计算建仓系统集成测试 <<<")
    print("==================================================")

    # 1. 测试风控拦截：现金不足
    print("\n[测试 1] 校验低现金风控拦截 (设定资金为 1000 元)...")
    trading_service.reset_account("AI", initial_capital=1000.0)
    res1 = auto_trader.execute_auto_trading(account_type="AI", max_buy_count=2)
    assert not res1["success"], "低现金未正确触发风控拦截"
    assert "不足以建仓" in res1["msg"], f"拦截提示信息不符: {res1['msg']}"
    print(f"  [PASS] 资金风控拦截生效: {res1['msg']}")

    # 2. 测试正常全流程自动建仓
    print("\n[测试 2] 重置 AI 账户至 100,000 元并执行 AI 一键自动建仓...")
    trading_service.reset_account("AI", initial_capital=100000.0)
    res2 = auto_trader.execute_auto_trading(account_type="AI", max_buy_count=2)
    assert res2["success"], f"自动建仓执行失败: {res2['msg']}"
    assert res2["executed_count"] >= 1, f"建仓数量不符合预期: {res2['executed_count']}"
    print(f"  [PASS] AI 自动建仓成功达成！撮合买入标的数: {res2['executed_count']}")

    # 检查买入标的明细与 100 股整数倍
    for item in res2["bought_items"]:
        sym = item["symbol"]
        amt = item["amount"]
        score = item["score"]
        val = item["total_value"]
        reason = item["reason"]
        assert amt > 0 and amt % 100 == 0, f"买入股数必须为 100 股整数倍: {amt}"
        assert val <= 35000.0, f"单票资金超出 30% 上限: {val}"
        print(f"  - 标的: {item['name']}({sym}), 买入: {amt} 股, 成交额: {val:.2f} 元, 置信分: {score:.1f}")
        print(f"    决策归因: {reason[:60]}...")

    # 3. 验证 T+1 交易纪律与流水记录
    print("\n[测试 3] 验证持仓 T+1 交易纪律锁定与成交流水记录...")
    positions = trading_service.get_positions("AI")
    assert len(positions) == res2["executed_count"], "持仓记录数量与执行建仓数量不一致"
    for pos in positions:
        assert pos["total_amount"] >= 100, "总持股数不正确"
        assert pos["available_amount"] == 0, f"A 股 T+1 交易纪律未生效: {pos['available_amount']}"
    print(f"  [PASS] 所有持仓 {len(positions)} 支标的均严格执行 T+1 当日冻结 (available_amount=0)。")

    trades = trading_service.get_trades_history("AI", limit=10)
    assert len(trades) >= res2["executed_count"], "流水记录数量不足"
    assert trades[0]["action"] == "BUY", "最新流水动作必须为 BUY"
    print(f"  [PASS] 成交流水核实无误: 最新买入记录 [{trades[0]['name']}] 佣金 {trades[0]['commission_fee']} 元。")

    # 4. 验证防重复建仓机制
    print("\n[测试 4] 验证防重复建仓机制 (再次触发自动建仓，应避开已有持仓)...")
    held_symbols_before = set([p["symbol"] for p in positions])
    res4 = auto_trader.execute_auto_trading(account_type="AI", max_buy_count=1)
    if res4["success"]:
        for item in res4["bought_items"]:
            assert item["symbol"] not in held_symbols_before, f"出现重复建仓已有标的: {item['symbol']}"
        print(f"  [PASS] 防重复机制有效: 成功避开已有持仓，增量建仓新标的: {res4['bought_items'][0]['name']}")
    else:
        print(f"  [INFO] 次轮未建仓: {res4['msg']}")

    # 5. 验证持仓上限拦截 (5 支上限)
    print("\n[测试 5] 验证持仓 5 支上限风控拦截...")
    # 手动补齐至 5 支持仓
    curr_pos = trading_service.get_positions("AI")
    curr_held = [p["symbol"] for p in curr_pos]
    fill_candidates = ["600000", "600036", "600519", "000858", "000001", "002415"]
    for sym in fill_candidates:
        if len(trading_service.get_positions("AI")) >= 5:
            break
        if sym not in curr_held:
            trading_service.buy_stock("AI", sym, 100, custom_price=10.0, reason="持仓补位测试")

    pos_full = trading_service.get_positions("AI")
    assert len(pos_full) == 5, f"持仓未达到 5 支: {len(pos_full)}"
    
    res5 = auto_trader.execute_auto_trading(account_type="AI", max_buy_count=1)
    assert not res5["success"], "达到 5 支持仓后未正确拦截自动建仓"
    assert "上限（5 支）" in res5["msg"], f"拦截信息不匹配: {res5['msg']}"
    print(f"  [PASS] 持仓上限风控拦截生效: {res5['msg']}")

    print("\n==================================================")
    print(">>> 恭喜！AI 自动计算建仓系统所有核心逻辑测试全部 PASS！<<<")
    print("==================================================")


if __name__ == "__main__":
    run_tests()
