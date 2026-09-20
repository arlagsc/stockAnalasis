# -*- coding: utf-8 -*-
"""AI 操盘技能 (SKILL) 自演进与交易归因反思引擎

核心功能：
1. 对仿真平仓交易进行量化盈亏归因与认知复盘 (Reflection)；
2. 驱动大模型总结提炼可执行的实战操盘军规 (Trading Skills)；
3. 动态维护本地 Skill 经验知识库并自适应注入后续 AI 推荐决策。
"""

import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import desc

from app.core.config import logger
from app.core.database import db_manager, TraderSkill
from app.data.fetcher import data_fetcher
from app.data.indicators import indicator_engine
from app.ai.llm_client import llm_client
from app.ai.prompts import (
    TRADE_REFLECTION_SYSTEM_PROMPT, TRADE_REFLECTION_USER_TEMPLATE
)
from app.ai.parser import output_parser

class SkillEngine:
    """AI 操盘技能自进化引擎单例"""

    def __init__(self):
        self._ensure_seed_skills()

    def _ensure_seed_skills(self):
        """若经验库为空，初始化注入高确定性实战交易经典军规"""
        session = db_manager.get_session()
        try:
            count = session.query(TraderSkill).count()
            if count == 0:
                seeds = [
                    TraderSkill(
                        category="趋势突破",
                        rule_title="放量突破颈线且回踩企稳战法",
                        rule_markdown="当标的股价放量突破前期平台颈线高点后，若缩量回踩20日生命线获得明显长下影线支撑，MACD维持红柱动能，属于高盈亏比加仓点，胜率较高。",
                        win_rate_score=82.5,
                        from_symbol="系统预置",
                        is_active=True,
                    ),
                    TraderSkill(
                        category="破位止损",
                        rule_title="跌破20日均线放量中阴次日早盘坚决止损",
                        rule_markdown="若持仓个股收盘有效跌破20日均线且成交量放大，说明短期多头防线瓦解。严禁幻想死扛，次日早盘冲高或平开时必须无条件执行纪律平仓，严格防范阴跌深套风险。",
                        win_rate_score=88.0,
                        from_symbol="系统预置",
                        is_active=True,
                    )
                ]
                session.add_all(seeds)
                session.commit()
                logger.info("已成功初始化系统预置操盘技能军规库。")
        except Exception as e:
            session.rollback()
            logger.error("初始化种子操盘技能异常: %s", str(e))
        finally:
            session.close()

    def reflect_on_trade(self, trade_summary: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """对已平仓的交易进行大模型深度反思与技能规则萃取"""
        symbol = str(trade_summary.get("symbol", "")).zfill(6)
        name = str(trade_summary.get("name", symbol))
        realized_pnl = float(trade_summary.get("realized_pnl", 0.0))
        realized_pct = float(trade_summary.get("realized_pct", 0.0))
        cost_price = float(trade_summary.get("cost_price", 0.0))
        sell_price = float(trade_summary.get("sell_price", 0.0))
        amount = int(trade_summary.get("amount", 0))
        account_type = str(trade_summary.get("account_type", "AI"))
        reason = str(trade_summary.get("reason", "周期调仓"))

        logger.info("启动交易归因反思引擎: [%s %s] 盈亏比: %.2f%%", symbol, name, realized_pct)

        # 获取技术面指标快照作为复盘输入
        tech_context = "暂无指标快照"
        try:
            kline_df = data_fetcher.fetch_stock_daily_kline(symbol, count=60)
            if not kline_df.empty:
                kline_with_ind = indicator_engine.calculate_all_indicators(kline_df)
                snap = indicator_engine.extract_latest_snapshot(kline_with_ind)
                tech_context = (
                    f"MA5={snap.get('ma5', 0.0):.2f}, MA20={snap.get('ma20', 0.0):.2f}, "
                    f"MACD={snap.get('macd', 0.0):.3f}, RSI6={snap.get('rsi6', 0.0):.1f}, "
                    f"布林中轨={snap.get('boll_mid', 0.0):.2f}"
                )
        except Exception as e:
            logger.debug("获取技术面快照用于复盘异常: %s", str(e))

        user_prompt = TRADE_REFLECTION_USER_TEMPLATE.format(
            name=name,
            symbol=symbol,
            account_type=account_type,
            cost_price=cost_price,
            sell_price=sell_price,
            amount=amount,
            realized_pnl=realized_pnl,
            realized_pct=realized_pct,
            reason=reason,
            tech_context=tech_context,
        )

        try:
            response_text = llm_client.chat_complete(
                system_prompt=TRADE_REFLECTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.2
            )
            parsed_json = output_parser.extract_json_block(response_text)
            
            # 若大模型返回标准 JSON
            if parsed_json and "rule_title" in parsed_json:
                category = parsed_json.get("category", "综合战术")
                title = parsed_json.get("rule_title", "实战纪律经验")
                content = parsed_json.get("rule_markdown", "")
                score = float(parsed_json.get("win_rate_score", 75.0))
            else:
                # 本地规则智能归纳兜底（未配置 API Key 或模型回复非 JSON 格式）
                if realized_pnl >= 0:
                    category = "止盈战法"
                    title = f"波段达标分批止盈纪律 ({name})"
                    content = f"标的【{name} ({symbol})】在达成目标位时果断减仓获利，实现盈利 {realized_pct:+.2f}%。战法核心：守住胜利果实，分批锁定波段利润，不贪婪盲目格局。"
                    score = 85.0
                else:
                    category = "止损风控"
                    title = f"破位果断截断亏损纪律 ({name})"
                    content = f"标的【{name} ({symbol})】在走势不及预期时及时平仓止损，控制亏损在 {realized_pct:+.2f}%。战法核心：纪律第一，绝不在下行趋势中补仓摊平成本，杜绝深套。"
                    score = 80.0

            session = db_manager.get_session()
            try:
                new_skill = TraderSkill(
                    category=category,
                    rule_title=title,
                    rule_markdown=content,
                    win_rate_score=score,
                    from_symbol=symbol,
                    is_active=True,
                )
                session.add(new_skill)
                session.commit()
                logger.info("交易反思成功沉淀新军规: 【%s】来自标的: %s", title, symbol)
                return {
                    "id": new_skill.id,
                    "category": category,
                    "rule_title": title,
                    "rule_markdown": content,
                    "win_rate_score": score,
                    "from_symbol": symbol,
                }
            finally:
                session.close()
        except Exception as e:
            logger.error("大模型反思归因执行异常: %s", str(e))
        return None

    def get_active_skills_prompt_block(self, limit: int = 5) -> str:
        """提取高胜率已激活技能，格式化为注入大模型的 Few-Shot 提示词块"""
        session = db_manager.get_session()
        try:
            skills = (
                session.query(TraderSkill)
                .filter_by(is_active=True)
                .order_by(desc(TraderSkill.win_rate_score), desc(TraderSkill.created_at))
                .limit(limit)
                .all()
            )
            if not skills:
                return ""

            lines = ["【历史实战沉淀的专属操盘军规库（高权重战法与避险经验）】:"]
            for i, s in enumerate(skills, 1):
                lines.append(f"{i}. [{s.category}] 【{s.rule_title}】")
                lines.append(f"   核心准则: {s.rule_markdown}")
            lines.append("请在本次决策中，严格贯彻上述军规纪律，主动规避历史大亏雷区，优先选择高胜率形态标的。")
            return "\n".join(lines)
        finally:
            session.close()

    def list_all_skills(self) -> List[Dict[str, Any]]:
        """获取所有已沉淀的操盘技能列表 (供前端界面展示)"""
        session = db_manager.get_session()
        try:
            skills = session.query(TraderSkill).order_by(desc(TraderSkill.created_at)).all()
            res = []
            for s in skills:
                res.append({
                    "id": s.id,
                    "category": s.category,
                    "rule_title": s.rule_title,
                    "rule_markdown": s.rule_markdown,
                    "win_rate_score": s.win_rate_score,
                    "from_symbol": s.from_symbol,
                    "is_active": s.is_active,
                    "created_at": s.created_at.strftime("%Y-%m-%d %H:%M") if s.created_at else "",
                })
            return res
        finally:
            session.close()

    def toggle_skill_active(self, skill_id: int, is_active: bool) -> bool:
        """人工启停指定操盘技能规则"""
        session = db_manager.get_session()
        try:
            sk = session.query(TraderSkill).filter_by(id=skill_id).first()
            if sk:
                sk.is_active = is_active
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            return False
        finally:
            session.close()

# 全局技能引擎单例
skill_engine = SkillEngine()
