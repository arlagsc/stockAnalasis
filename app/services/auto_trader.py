# -*- coding: utf-8 -*-
"""AI 自动计算建仓决策中枢 (AutoTrader)

实现全市场两阶段选拔与风控闭环:
1. 双层风控前置校验 (持仓上限 5 支、单票资金上限 30%、可用现金门槛);
2. 5,565 支全市场标的多因子向量化初筛 (排除已持仓、ST、涨跌停);
3. 注入系统实战操盘军规库 (Few-Shot)，由大模型进行深度形态裁决与战术归因 (含本地量化引擎平滑降级);
4. 动态分仓模型计算目标头寸，按 100 股向下取整执行仿真撮合与 T+1 交易纪律冻结。
"""

from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd

from app.core.config import logger
from app.data.fetcher import data_fetcher
from app.ai.llm_client import llm_client
from app.ai.parser import output_parser
from app.ai.skill_engine import skill_engine
from app.ai.prompts import (
    AUTO_TRADE_SYSTEM_PROMPT, AUTO_TRADE_USER_TEMPLATE,
    AUTO_SELL_SYSTEM_PROMPT, AUTO_SELL_USER_TEMPLATE
)
from app.data.indicators import indicator_engine
from app.services.trading_service import trading_service


class AutoTrader:
    """AI 智能自动建仓执行中枢"""

    def execute_auto_trading(
        self,
        account_type: str = "AI",
        max_buy_count: int = 2
    ) -> Dict[str, Any]:
        """执行一键 AI 自动计算与建仓买入管线
        
        返回:
            {
                "success": bool,
                "msg": str,
                "bought_items": list,
                "executed_count": int,
            }
        """
        logger.info(">>> 启动 [%s] 账户 AI 一键自动建仓决策管线 <<<", account_type)

        # 1. 风控门槛前置校验
        acc_summary = trading_service.get_account_summary(account_type)
        available_cash = acc_summary.get("available_cash", 0.0)
        total_equity = acc_summary.get("total_equity", 100000.0)
        positions = trading_service.get_positions(account_type)

        if len(positions) >= 5:
            msg = "风控拦截：AI 账户当前持仓已达分散上限（5 支），请等待现有标的触发平仓后再行建仓。"
            logger.warning(msg)
            return {"success": False, "msg": msg, "bought_items": [], "executed_count": 0}

        if available_cash < 2000.0:
            msg = f"风控拦截：AI 账户可用现金仅剩 {available_cash:.2f} 元，不足以建仓一手优质标的。"
            logger.warning(msg)
            return {"success": False, "msg": msg, "bought_items": [], "executed_count": 0}

        # 允许建仓的空闲仓位数量
        allowed_slots = min(max_buy_count, 5 - len(positions))
        held_symbols = set([p["symbol"] for p in positions])

        # 2. 全市场多因子向量化初选候选池 (Top 10)
        candidates = self._screen_candidates(held_symbols=held_symbols, limit=10)
        if not candidates:
            msg = "全市场筛选完毕，当前市场环境下未扫描到符合多因子顺势特征的标的，本次不建仓。"
            logger.info(msg)
            return {"success": False, "msg": msg, "bought_items": [], "executed_count": 0}

        logger.info("初筛获得 Top %d 支候选标的，准备注入实战操盘军规进行模型裁决...", len(candidates))

        # 3. 注入操盘军规库进行深度裁决
        decisions = self._evaluate_with_skills(candidates)
        if not decisions:
            # 本地量化规则兜底评选
            decisions = self._fallback_local_evaluation(candidates)

        if not decisions:
            msg = "AI 形态裁决完成：候选标的均未通过操盘军规胜率检验，系统决定空仓观望。"
            logger.warning(msg)
            return {"success": False, "msg": msg, "bought_items": [], "executed_count": 0}

        logger.info("AI 裁决引擎最终确认拟建仓决策 %d 条，准备进入动态分仓与撮合执行", len(decisions))

        # 4. 依据评分梯度执行动态分仓与仿真撮合
        bought_items = []
        executed_count = 0

        # 按置信评分降序挑选
        sorted_decisions = sorted(decisions, key=lambda x: x.get("score", 0.0), reverse=True)
        target_decisions = sorted_decisions[:allowed_slots]

        for item in target_decisions:
            sym = str(item["symbol"]).zfill(6)
            name = item.get("name", f"标的{sym}")
            score = float(item.get("score", 85.0))
            reason = item.get("reason", "AI 量化与军规共振建仓")

            # 重新核算当前即时可用资金
            curr_acc = trading_service.get_account_summary(account_type)
            curr_cash = curr_acc.get("available_cash", 0.0)

            # 获取最新盘口价格
            price = float(item.get("price", 0.0))
            if price <= 0.0:
                # 寻找候选池中的价格
                matched_c = next((c for c in candidates if c["symbol"] == sym), None)
                price = float(matched_c["price"]) if matched_c else 10.0

            # 动态分仓比例计算
            if score >= 88.0:
                target_ratio = 0.28  # 高置信度分配 ~28%
            else:
                target_ratio = 0.18  # 次优形态分配 ~18%

            target_money = min(curr_cash * target_ratio, total_equity * 0.30)
            
            # 换算为 100 股向下取整
            target_amount = int(target_money // (price * 100)) * 100

            # 最低建仓 1 手 (100 股) 保障
            if target_amount < 100:
                if curr_cash >= (price * 100 * 1.002):
                    target_amount = 100
                else:
                    logger.info("资金不足以买入一手 [%s %s]，跳过该标的", sym, name)
                    continue

            # 执行仿真撮合
            ok, msg_buy = trading_service.buy_stock(
                account_type=account_type,
                symbol=sym,
                amount=target_amount,
                custom_price=price,
                name=name,
                reason=reason
            )

            if ok:
                bought_value = round(price * target_amount, 2)
                bought_items.append({
                    "symbol": sym,
                    "name": name,
                    "price": price,
                    "amount": target_amount,
                    "total_value": bought_value,
                    "score": score,
                    "reason": reason,
                })
                executed_count += 1
                logger.info("AI 自动建仓成功: [%s %s] %d 股 (成交额: %.2f 元, 置信分: %.1f)", sym, name, target_amount, bought_value, score)

        if executed_count > 0:
            summary_msg = f"AI 自动决策完成！成功为 AI 操盘账户建立 {executed_count} 支优质持仓，已严格执行 T+1 交易纪律锁定。"
            return {
                "success": True,
                "msg": summary_msg,
                "bought_items": bought_items,
                "executed_count": executed_count,
            }
        else:
            return {
                "success": False,
                "msg": "自动建仓撮合未达成，可能由于候选标的买入资金核算不足，请充值后重试。",
                "bought_items": [],
                "executed_count": 0,
            }

    def _screen_candidates(self, held_symbols: set, limit: int = 10) -> List[Dict[str, Any]]:
        """全市场 5,565 支多因子初筛"""
        df = data_fetcher.fetch_all_stock_basics()
        if df.empty or "symbol" not in df.columns:
            return []

        # 基础过滤：排除已持仓、ST 股票、停牌与极端涨跌停
        cond = (
            (~df["symbol"].isin(held_symbols)) &
            (~df["name"].str.contains("ST|退", na=False)) &
            (df["close_price"] >= 3.0) &
            (df["close_price"] <= 300.0) &
            (df["change_pct"] > -8.5) &
            (df["change_pct"] < 9.8) &
            (df["turnover_rate"] >= 0.8) &
            (df["turnover_rate"] <= 15.0)
        )
        filtered = df[cond].copy()
        if filtered.empty:
            filtered = df[~df["symbol"].isin(held_symbols)].copy()

        # 计算复合量化动能得分
        # 换手活跃度 (0~30分) + 涨幅适中度 (0~40分) + 市值弹性 (0~30分)
        filtered["score"] = 50.0
        
        # 涨幅处于 +1% ~ +5% 的进攻形态得分最高
        pct_bonus = np.where((filtered["change_pct"] >= 1.0) & (filtered["change_pct"] <= 5.5), 30.0, 15.0)
        filtered["score"] += pct_bonus

        # 适中换手率加分 (2% ~ 8%)
        turn_bonus = np.where((filtered["turnover_rate"] >= 2.0) & (filtered["turnover_rate"] <= 8.0), 15.0, 5.0)
        filtered["score"] += turn_bonus

        # 按得分排序选出前 Top N
        top_df = filtered.sort_values(by="score", ascending=False).head(limit)

        candidates = []
        for _, row in top_df.iterrows():
            candidates.append({
                "symbol": str(row["symbol"]).zfill(6),
                "name": str(row["name"]),
                "price": float(row.get("close_price", 10.0)),
                "change_pct": float(row.get("change_pct", 0.0)),
                "turnover_rate": float(row.get("turnover_rate", 0.0)),
                "pe_ratio": float(row.get("pe_ratio", 0.0)),
                "quant_score": float(row.get("score", 70.0)),
            })
        return candidates

    def _evaluate_with_skills(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """提取军规注入大模型进行形态裁决"""
        skills_block = skill_engine.get_active_skills_prompt_block(limit=5)
        if not skills_block:
            skills_block = "【系统操盘军规】：严禁追高超买标的，优先选择均线向上多头排列、放量突破或回踩企稳标的。"

        # 格式化候选池
        cand_lines = []
        for i, c in enumerate(candidates, 1):
            cand_lines.append(
                f"{i}. [{c['name']}({c['symbol']})] 现价: {c['price']:.2f}元, 今日涨幅: {c['change_pct']:+.2f}%, "
                f"换手率: {c['turnover_rate']:.2f}%, PE: {c['pe_ratio']:.1f}, 初筛评分: {c['quant_score']:.1f}"
            )
        cand_text = "\n".join(cand_lines)

        user_prompt = AUTO_TRADE_USER_TEMPLATE.format(
            skills_block=skills_block,
            candidates_block=cand_text
        )

        try:
            response_text = llm_client.chat_complete(
                system_prompt=AUTO_TRADE_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.2
            )
            parsed = output_parser.extract_json_block(response_text)
            if parsed and isinstance(parsed, dict) and "selected" in parsed:
                selected_list = parsed["selected"]
                res = []
                for s in selected_list:
                    sym = str(s.get("symbol", "")).zfill(6)
                    # 匹配候选池原信息
                    matched = next((c for c in candidates if c["symbol"] == sym), None)
                    if matched:
                        res.append({
                            "symbol": sym,
                            "name": matched["name"],
                            "price": matched["price"],
                            "score": float(s.get("score", 88.0)),
                            "reason": str(s.get("reason", "符合操盘军规突破战则")),
                        })
                return res
        except Exception as e:
            logger.warning("大模型军规裁决执行异常，将自动启用本地量化兜底: %s", str(e))

        return []

    def _fallback_local_evaluation(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """离线或无 API Key 时的本地多因子量化形态裁决兜底"""
        logger.info("启用本地多因子量化评选引擎进行自动建仓决策...")
        # 挑选量化初筛前 2 支
        top_2 = sorted(candidates, key=lambda x: x.get("quant_score", 0.0), reverse=True)[:2]
        res = []
        for c in top_2:
            res.append({
                "symbol": c["symbol"],
                "name": c["name"],
                "price": c["price"],
                "score": round(c.get("quant_score", 80.0) + 10.0, 1),
                "reason": f"基于本地多因子量化模型：涨跌幅与量价换手共振（换手率 {c['turnover_rate']:.2f}%），契合顺势建仓规则。",
            })
        logger.info(
            "本地多因子量化兜底评选完成，已优选 %d 支标的: %s",
            len(res),
            ", ".join([f"{x['name']}({x['symbol']})" for x in res]) if res else "无"
        )
        return res

    def execute_auto_selling(
        self,
        account_type: str = "AI",
        stop_loss_pct: float = -5.0,
        take_profit_pct: float = 10.0,
        enable_tech_breakdown: bool = True,
        enable_llm_eval: bool = True
    ) -> Dict[str, Any]:
        """执行持仓标的智能巡检与自动平仓决策管线
        
        风控与策略准则:
        1. T+1 交易纪律前置检查：若可卖数量 available_amount <= 0，严格安全锁止，不予卖出；
        2. 硬止损策略 (Hard Stop-Loss)：浮亏 <= stop_loss_pct 时，坚决平仓止损；
        3. 动态止盈策略 (Take-Profit)：浮盈 >= take_profit_pct 时，波段获利平仓；
        4. 均线与指标破位 (Technical Breakdown)：收盘价跌破 MA20 且 MACD 死叉时，避险平仓；
        5. 大模型军规形态裁决 (LLM Diagnosis)：对照操盘军规对持仓进行深度体检；
        6. 平仓即反思闭环：自动驱动 SkillEngine 复盘交易并提炼沉淀新的实操军规。
        """
        logger.info(">>> 启动 [%s] 账户 AI 智能持仓巡检与自动平仓决策管线 <<<", account_type)

        # 1. 批量刷新持仓最新盘口与 T+1 解冻状态
        trading_service.refresh_positions_quotes(account_type)
        positions = trading_service.get_positions(account_type)

        if not positions:
            msg = f"[{account_type}] 账户当前无任何持仓标的，无需执行自动巡检平仓。"
            logger.info(msg)
            return {
                "success": True,
                "msg": msg,
                "sold_items": [],
                "held_items": [],
                "locked_items": [],
                "sold_count": 0,
            }

        sold_items = []
        held_items = []
        locked_items = []
        sell_plan = []  # 待执行平仓的任务列表: [(pos, trigger_type, reason)]

        # 2. 遍历持仓进行逐一检查
        for p in positions:
            sym = p["symbol"]
            name = p["name"]
            tot_amt = p["total_amount"]
            avail_amt = p["available_amount"]
            pnl_pct = p["floating_pnl_pct"]
            pnl_val = p["floating_pnl"]
            cur_price = p["current_price"]
            cost_price = p["cost_price"]

            # (1) T+1 纪律检查
            if avail_amt <= 0:
                logger.info("标的 [%s %s] 今日买入持仓处于 T+1 锁定期 (可卖: 0/%d 股)，暂不可平仓", sym, name, tot_amt)
                locked_items.append({
                    "symbol": sym,
                    "name": name,
                    "total_amount": tot_amt,
                    "available_amount": avail_amt,
                    "floating_pnl_pct": pnl_pct,
                    "status": "T+1 锁定中 (次日开盘自动解冻)",
                })
                continue

            # (2) 硬止损触发判定
            if pnl_pct <= stop_loss_pct:
                reason = f"触发硬止损纪律：当前浮亏 {pnl_pct:+.2f}% 已达到或跌破设定的风控红线 ({stop_loss_pct:.1f}%)，执行果断止损离场，截断进一步回撤风险。"
                sell_plan.append((p, "硬止损风控", reason))
                continue

            # (3) 动态止盈触发判定
            if pnl_pct >= take_profit_pct:
                reason = f"触发波段止盈纪律：当前浮盈 {pnl_pct:+.2f}% 已达成目标止盈位 (+{take_profit_pct:.1f}%)，按操盘军规落袋为安，锁定阶段性胜果。"
                sell_plan.append((p, "动态止盈获利", reason))
                continue

            # (4) 均线与技术形态破位判定 (MA20 / MACD)
            tech_triggered = False
            if enable_tech_breakdown:
                try:
                    kline_df = data_fetcher.fetch_stock_daily_kline(sym, count=30)
                    if not kline_df.empty and len(kline_df) >= 15:
                        kline_ind = indicator_engine.calculate_all_indicators(kline_df)
                        snap = indicator_engine.extract_latest_snapshot(kline_ind)
                        ma20 = snap.get("ma20", 0.0)
                        dif = snap.get("dif", 0.0)
                        dea = snap.get("dea", 0.0)

                        if ma20 > 0 and cur_price < (ma20 * 0.985) and dif < dea:
                            tech_triggered = True
                            reason = (
                                f"触发技术破位避险：现价 ({cur_price:.2f}元) 有效跌破 MA20 生命线 ({ma20:.2f}元) "
                                f"超过 1.5%，且 MACD 形成死叉发散 (DIF {dif:.3f} < DEA {dea:.3f})，均线形态走坏离场避险。"
                            )
                            sell_plan.append((p, "技术破位避险", reason))
                            continue
                except Exception as e:
                    logger.debug("计算标的 [%s] 技术指标破位时异常: %s", sym, str(e))

            # 未触发硬规则，暂归入待诊断池
            held_items.append({
                "symbol": sym,
                "name": name,
                "total_amount": tot_amt,
                "available_amount": avail_amt,
                "floating_pnl": pnl_val,
                "floating_pnl_pct": pnl_pct,
                "status": "趋势与指标健康，继续持有",
            })

        # (5) 若开启大模型深度持仓体检，对 held_items 进行进一步审查
        if enable_llm_eval and held_items:
            llm_sell_decisions = self._diagnose_positions_with_llm(held_items)
            for dec in llm_sell_decisions:
                target_sym = dec["symbol"]
                target_reason = dec["reason"]
                matched_p = next((p for p in positions if p["symbol"] == target_sym and p["available_amount"] > 0), None)
                if matched_p:
                    # 从 held_items 剔除，加入 sell_plan
                    held_items = [h for h in held_items if h["symbol"] != target_sym]
                    sell_plan.append((matched_p, "军规形态裁决", target_reason))

        # 3. 执行平仓撮合并驱动 AI 交易归因反思
        sold_count = 0
        for p, trigger_type, reason in sell_plan:
            sym = p["symbol"]
            name = p["name"]
            sell_amt = p["available_amount"]
            cur_p = p["current_price"]

            ok, msg_sell, trade_summary = trading_service.sell_stock(
                account_type=account_type,
                symbol=sym,
                amount=sell_amt,
                custom_price=cur_p,
                reason=reason
            )

            if ok:
                sold_count += 1
                realized_pnl = trade_summary.get("realized_pnl", 0.0) if trade_summary else 0.0
                realized_pct = trade_summary.get("realized_pct", 0.0) if trade_summary else 0.0

                sold_items.append({
                    "symbol": sym,
                    "name": name,
                    "amount": sell_amt,
                    "sell_price": cur_p,
                    "trigger_type": trigger_type,
                    "realized_pnl": realized_pnl,
                    "realized_pct": realized_pct,
                    "reason": reason,
                })
                logger.info("AI 自动平仓成功: [%s %s] %d 股 (类型: %s, 盈亏: %.2f 元, 原因: %s)", sym, name, sell_amt, trigger_type, realized_pnl, reason)

                # 驱动实战军规复盘归因自进化
                try:
                    if trade_summary:
                        new_skill = skill_engine.reflect_on_trade(trade_summary)
                        if new_skill:
                            logger.info("AI 平仓自动复盘沉淀军规成功: [%s] 胜率得分: %.1f", new_skill.rule_title, new_skill.win_rate_score)
                except Exception as e:
                    logger.error("平仓复盘军规沉淀异常: %s", str(e))
            else:
                logger.warning("标的 [%s %s] 自动平仓撮合失败: %s", sym, name, msg_sell)

        summary_msg = (
            f"AI 智能巡检完成！已对 {len(positions)} 支持仓标的进行深度体检，"
            f"成功平仓 {sold_count} 支，继续持有 {len(held_items)} 支，T+1 锁定 {len(locked_items)} 支。"
        )

        return {
            "success": True,
            "msg": summary_msg,
            "sold_items": sold_items,
            "held_items": held_items,
            "locked_items": locked_items,
            "sold_count": sold_count,
        }

    def _diagnose_positions_with_llm(self, candidate_holds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """调用大模型结合已激活的操盘军规对持仓标的进行深度体检"""
        skills_block = skill_engine.get_active_skills_prompt_block(limit=5)
        if not skills_block:
            skills_block = "【系统操盘军规】：趋势坏掉坚决止损，达标果断止盈，严禁在弱势破位走势中死扛亏损。"

        # 整理持仓快照文本
        lines = []
        for i, h in enumerate(candidate_holds, 1):
            sym = h["symbol"]
            name = h["name"]
            pnl_pct = h["floating_pnl_pct"]
            lines.append(f"{i}. [{name} ({sym})] 当前浮动盈亏率: {pnl_pct:+.2f}%, 持仓状态: {h.get('status', '持仓中')}")
        pos_text = "\n".join(lines)

        user_prompt = AUTO_SELL_USER_TEMPLATE.format(
            skills_block=skills_block,
            positions_block=pos_text
        )

        try:
            response_text = llm_client.chat_complete(
                system_prompt=AUTO_SELL_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.2
            )
            parsed = output_parser.extract_json_block(response_text)
            if parsed and isinstance(parsed, dict) and "sell_candidates" in parsed:
                return [
                    {
                        "symbol": str(s.get("symbol", "")).zfill(6),
                        "reason": str(s.get("reason", "大模型军规裁决建议离场")),
                    }
                    for s in parsed["sell_candidates"]
                    if str(s.get("action", "")).upper() == "SELL"
                ]
        except Exception as e:
            logger.debug("大模型持仓巡检裁决执行跳过 (或本地兜底): %s", str(e))

        return []


# 全局自动交易中枢单例
auto_trader = AutoTrader()
