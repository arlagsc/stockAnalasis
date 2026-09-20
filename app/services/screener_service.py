# -*- coding: utf-8 -*-
"""两阶段智能筛选与自然语言选股引擎

实现两阶段筛选漏斗：
第一阶段：通过本地 Pandas 向量化引擎高速执行结构化多因子筛选，
将全市场 5000+ 标的快速降维至 20~50 候选池；
第二阶段：支持自然语言诉求接入大模型自动编译成规则方案 (NL-to-Filter)。
"""

from typing import List, Dict, Any, Tuple, Optional
import pandas as pd

from app.core.config import logger
from app.ai.prompts import NL_TO_FILTER_SYSTEM_PROMPT
from app.ai.parser import output_parser, FilterPlan, FilterRule
from app.ai.llm_client import llm_client
from app.services.data_service import data_service

class ScreenerService:
    """智能选股与两阶段漏斗引擎"""

    def __init__(self):
        # 预设常用量化策略方案
        self.preset_strategies: Dict[str, FilterPlan] = {
            "低估值稳健白马": FilterPlan(
                explanation="市盈率 <= 25，市值 >= 500 亿，日内涨幅大于 0%",
                rules=[
                    FilterRule(field="pe_ratio", operator="<=", value=25.0),
                    FilterRule(field="pe_ratio", operator=">", value=0.0),
                    FilterRule(field="total_market_val", operator=">=", value=500.0),
                    FilterRule(field="change_pct", operator=">=", value=0.0),
                ],
                sort_by="pe_ratio",
                sort_ascending=True,
                limit=30,
            ),
            "多头突破高弹性": FilterPlan(
                explanation="今日涨幅 >= 2%，换手率 >= 1.5%，总市值 >= 100 亿",
                rules=[
                    FilterRule(field="change_pct", operator=">=", value=2.0),
                    FilterRule(field="turnover_rate", operator=">=", value=1.5),
                    FilterRule(field="total_market_val", operator=">=", value=100.0),
                ],
                sort_by="change_pct",
                sort_ascending=False,
                limit=30,
            ),
            "超跌潜力关注": FilterPlan(
                explanation="市盈率 <= 35，市净率 <= 3.0，今日涨跌幅在 -1% 至 2% 之间筑底",
                rules=[
                    FilterRule(field="pe_ratio", operator="<=", value=35.0),
                    FilterRule(field="pe_ratio", operator=">", value=0.0),
                    FilterRule(field="pb_ratio", operator="<=", value=3.0),
                    FilterRule(field="change_pct", operator=">=", value=-1.0),
                ],
                sort_by="pb_ratio",
                sort_ascending=True,
                limit=30,
            ),
        }

    def execute_filter_plan(self, plan: FilterPlan, source_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """根据结构化规则方案在本地 DataFrame 执行高速筛选"""
        df = source_df if source_df is not None else data_service.get_stock_universe()
        if df.empty:
            logger.warning("股票基础池为空，筛选结果为空。")
            return pd.DataFrame()

        filtered_df = df.copy()

        for rule in plan.rules:
            field = rule.field.lower()
            op = rule.operator.strip()
            val = rule.value

            if field not in filtered_df.columns:
                logger.debug("字段 [%s] 不在当前数据集，跳过该规则", field)
                continue

            try:
                val_num = float(val) if isinstance(val, (int, float, str)) and str(val).replace(".", "", 1).isdigit() else val
                if op in (">", "gt"):
                    filtered_df = filtered_df[filtered_df[field] > val_num]
                elif op in (">=", "gte"):
                    filtered_df = filtered_df[filtered_df[field] >= val_num]
                elif op in ("<", "lt"):
                    filtered_df = filtered_df[filtered_df[field] < val_num]
                elif op in ("<=", "lte"):
                    filtered_df = filtered_df[filtered_df[field] <= val_num]
                elif op in ("==", "=", "eq"):
                    filtered_df = filtered_df[filtered_df[field] == val_num]
            except Exception as e:
                logger.warning("执行单条过滤规则失败 [%s %s %s]: %s", field, op, val, str(e))

        # 排序处理
        sort_col = plan.sort_by if plan.sort_by in filtered_df.columns else "change_pct"
        if sort_col in filtered_df.columns:
            filtered_df = filtered_df.sort_values(by=sort_col, ascending=plan.sort_ascending)

        # 限制数量
        if plan.limit and plan.limit > 0:
            filtered_df = filtered_df.head(plan.limit)

        logger.info("筛选规则执行完毕: 符合条件的候选标的数量为: %d", len(filtered_df))
        return filtered_df.reset_index(drop=True)

    def screen_by_natural_language(self, user_query: str) -> Tuple[FilterPlan, pd.DataFrame]:
        """自然语言选股 (NL-to-Filter)：LLM 解析自然语言输入为结构化 Plan 并执行过滤"""
        logger.info("用户提交自然语言选股指令: %s", user_query)
        user_prompt = f"用户输入选股诉求：{user_query}\n请按规范解析并返回严格的 JSON 筛选规则。"
        
        # 调用大模型生成规则
        raw_response = llm_client.chat_complete(
            system_prompt=NL_TO_FILTER_SYSTEM_PROMPT,
            user_prompt=user_prompt
        )
        
        # 解析为强类型对象
        plan = output_parser.parse_filter_plan(raw_response)
        logger.info("成功编译筛选策略: %s, 规则条数: %d", plan.explanation, len(plan.rules))

        # 执行本地过滤
        result_df = self.execute_filter_plan(plan)
        return plan, result_df

# 单例
screener_service = ScreenerService()
