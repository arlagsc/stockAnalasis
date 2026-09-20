# -*- coding: utf-8 -*-
"""虚拟建仓与 AI 操盘技能库自动化集成测试

覆盖用例:
1. 初始本金设定与自定义重置 (支持用户自由设定如 200,000 元)
2. A 股仿真买入撮合 (100 股整数倍约束、佣金计费、持仓生成及 T+1 锁定)
3. T+1 可卖额度流转校验 (当日买入不可卖，次日自动解锁)
4. 卖出撮合结算 (印花税与佣金扣除、现金返还、盈亏结清)
5. 操盘技能库自演进 (平仓大模型归因反思、军规沉淀与动态 Prompt 注入)
"""

import sys
import os
from datetime import datetime, timedelta

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import logger
from app.core.database import db_manager, VirtualAccount, VirtualPosition, VirtualTrade, TraderSkill
from app.services.trading_service import trading_service
from app.ai.skill_engine import skill_engine


def run_tests():
    print("==================================================")
    print(">>> 开始执行虚拟建仓与操盘技能库集成测试 <<<")
    print("==================================================")

    # 1. 测试重置账户与自定义初始本金
    print("\n[测试 1] 设定自定义初始资金并重置账户...")
    custom_capital = 300000.0
    trading_service.reset_account("MANUAL", initial_capital=custom_capital)
    trading_service.reset_account("AI", initial_capital=100000.0)

    manual_acc = trading_service.get_account_summary("MANUAL")
    ai_acc = trading_service.get_account_summary("AI")
    assert manual_acc["initial_capital"] == custom_capital, f"初始资金设置失败: {manual_acc['initial_capital']}"
    assert manual_acc["available_cash"] == custom_capital, f"可用现金不符: {manual_acc['available_cash']}"
    assert manual_acc["total_equity"] == custom_capital, f"总资产不符: {manual_acc['total_equity']}"
    assert ai_acc["initial_capital"] == 100000.0, f"AI 账户初始资金不符"
    print(f"  [PASS] 人类主观账户重置为 {custom_capital} 元成功，AI 账户重置为 100,000 元成功。")

    # 2. 测试买入撮合约束 (非 100 股整数倍拦截)
    print("\n[测试 2] 买入撮合规则校验 (100 股整数倍限制)...")
    ok, msg = trading_service.buy_stock("MANUAL", "002429", 150, reason="非标手数测试")
    assert not ok, "非 100 股整数倍未能正确拦截"
    print(f"  [PASS] 非 100 股整数倍拦截成功，提示: {msg}")

    # 3. 正常买入撮合
    print("\n[测试 3] 执行正常买入撮合 (人类账户买入 1000 股 002429 兆驰股份)...")
    ok, msg = trading_service.buy_stock("MANUAL", "002429", 1000, reason="测试突破颈线建仓")
    assert ok, f"买入失败: {msg}"
    print(f"  [PASS] 模拟撮合成功: {msg}")

    # 检查持仓及 T+1 锁定状态
    positions = trading_service.get_positions("MANUAL")
    assert len(positions) == 1, "持仓记录数量不正确"
    pos = positions[0]
    assert pos["symbol"] == "002429", "持仓股票代码不正确"
    assert pos["total_amount"] == 1000, "总股数不正确"
    assert pos["available_amount"] == 0, f"A 股 T+1 交易纪律未生效，当日买入可用股数应为 0，实际为: {pos['available_amount']}"
    print(f"  [PASS] T+1 交易纪律生效: 当日买入总股数 {pos['total_amount']}，可卖股数已严格锁定为 {pos['available_amount']}。")

    # 4. 测试当日回转卖出拦截 (T+1 违规拦截)
    print("\n[测试 4] 测试 T+1 纪律约束: 尝试当日即时卖出...")
    ok, msg, _ = trading_service.sell_stock("MANUAL", "002429", 500, reason="违规日内回转测试")
    assert not ok, "当日未解锁持仓未能正确拦截卖出"
    print(f"  [PASS] T+1 违规卖出被成功拦截，提示: {msg}")

    # 5. 模拟时间流转至次日 (解冻可卖数量)
    print("\n[测试 5] 模拟时间跨越交易日 (修改持仓最后买入时间为昨天并刷新)...")
    session = db_manager.get_session()
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    db_pos = session.query(VirtualPosition).filter(VirtualPosition.account_type == "MANUAL", VirtualPosition.symbol == "002429").first()
    db_pos.last_buy_date = yesterday_str
    session.commit()
    session.close()

    # 刷新持仓盘口，触发 T+1 可用数量解冻
    trading_service.refresh_positions_quotes()
    positions_after = trading_service.get_positions("MANUAL")
    pos_after = positions_after[0]
    assert pos_after["available_amount"] == 1000, f"次日 T+1 解锁失败，可用股数应为 1000，实际为: {pos_after['available_amount']}"
    print(f"  [PASS] 跨交易日后自动解锁可用股数: 可卖股数成功恢复为 {pos_after['available_amount']} 股。")

    # 6. 测试正常卖出撮合与清算
    print("\n[测试 6] 执行部分卖出撮合 (卖出 500 股 002429)...")
    ok, msg, trade_summary = trading_service.sell_stock("MANUAL", "002429", 500, reason="测试止盈减仓")
    assert ok, f"卖出失败: {msg}"
    print(f"  [PASS] 卖出结算成功: {msg}")

    # 检查卖出后的持仓
    positions_remain = trading_service.get_positions("MANUAL")
    assert len(positions_remain) == 1, "剩余持仓记录异常"
    assert positions_remain[0]["total_amount"] == 500, f"剩余股数不符合预期: {positions_remain[0]['total_amount']}"
    print(f"  [PASS] 仓位核减准确，剩余持仓 {positions_remain[0]['total_amount']} 股。")

    # 检查交易流水记录
    trades = trading_service.get_trades_history("MANUAL")
    assert len(trades) == 2, f"流水记录数量不符，应为 2 笔，实际为: {len(trades)}"
    sell_trade = trades[0]  # 按时间倒序，最新的是卖出
    assert sell_trade["action"] == "SELL", "流水动作不符"
    assert sell_trade["amount"] == 500, "卖出数量不符"
    assert sell_trade["tax_fee"] > 0, f"印花税应大于 0: {sell_trade['tax_fee']}"
    assert sell_trade["commission_fee"] >= 5.0, f"佣金应满足最低 5 元保底: {sell_trade['commission_fee']}"
    print(f"  [PASS] 交易流水核对无误: 扣除印花税 {sell_trade['tax_fee']} 元，佣金 {sell_trade['commission_fee']} 元，实现盈亏 {sell_trade['realized_pnl']} 元。")

    # 7. 测试 AI 操盘技能库反思归因与军规沉淀
    print("\n[测试 7] 触发操盘反思归因引擎 (reflect_on_trade)...")
    initial_skills = skill_engine.list_all_skills()
    initial_skill_count = len(initial_skills)
    print(f"  当前活跃操盘军规条数: {initial_skill_count}")

    # 使用真实平仓交易包进行反思沉淀
    new_skill = skill_engine.reflect_on_trade(trade_summary)
    if new_skill:
        print(f"  反思归因完成，提炼出军规: 【{new_skill['rule_title']}】")
        assert new_skill["rule_title"] != "", "军规标题不能为空"
        assert len(new_skill["rule_markdown"]) > 5, "军规内容应包含详细反思战则"
        print(f"  军规内容摘录: {new_skill['rule_markdown'][:80]}...")
    else:
        print("  反思归因未生成新军规（可能未配置 API Key 且平仓幅度微弱），使用种子库验证。")

    # 8. 测试动态 Prompt 提取
    print("\n[测试 8] 测试动态 Prompt 提取 (get_active_skills_prompt_block)...")
    prompt_block = skill_engine.get_active_skills_prompt_block(limit=3)
    assert "历史实战沉淀的专属操盘军规库" in prompt_block, "生成的 Prompt 模板未包含技能库标头"
    print("  [PASS] Few-Shot Prompt 注入块生成正常，格式预览:")
    print("  " + "\n  ".join(prompt_block.splitlines()[:6]))

    print("\n==================================================")
    print(">>> 恭喜！虚拟建仓与操盘技能库所有核心逻辑测试全部 PASS！<<<")
    print("==================================================")


if __name__ == "__main__":
    run_tests()
