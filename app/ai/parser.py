# -*- coding: utf-8 -*-
"""大模型输出解析与容错校验模块

负责从大模型返回的自由文本或 Markdown 中提取合规的 JSON 数据，
并基于 Pydantic 执行结构化严格校验。提供后备降级策略，确保极端情况下不抛出异常。
"""

import re
import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from app.core.config import logger

class FilterRule(BaseModel):
    """单条量化过滤条件"""
    field: str = Field(description="过滤字段名称")
    operator: str = Field(description="比较操作符")
    value: Any = Field(description="阈值（数值或列表）")

class FilterPlan(BaseModel):
    """自然语言编译后的筛选方案"""
    explanation: str = Field(default="规则筛选方案", description="规则解析说明")
    rules: List[FilterRule] = Field(default_factory=list, description="规则集合")
    sort_by: Optional[str] = Field(default="change_pct", description="排序基准字段")
    sort_ascending: bool = Field(default=False, description="是否升序排列")
    limit: int = Field(default=30, description="最大展示记录数")

class RecommendedStock(BaseModel):
    """推荐标的实体"""
    symbol: str = Field(description="股票代码")
    name: str = Field(description="股票名称")
    score: float = Field(default=80.0, description="模型综合评分(0-100)")
    reasons: List[str] = Field(default_factory=list, description="入选推荐理由列表")
    risk_warnings: str = Field(default="注意市场整体波动风险", description="风险提示")

class RecommendResponse(BaseModel):
    """大模型精排推荐响应格式"""
    market_summary: str = Field(default="市场热点分化，结构性机会为主", description="市场概况")
    recommended_stocks: List[RecommendedStock] = Field(default_factory=list, description="精选推荐列表")

class OutputParser:
    """大模型响应输出解析器"""

    @staticmethod
    def extract_json_block(text: str) -> Optional[Dict[str, Any]]:
        """从模型返回的可能包含 Markdown 标记或深度思考链 (Thinking) 的文本中提取有效 JSON 字典"""
        if not text:
            return None

        # 1. 预处理：剥离思考模型常见的 <think>...</think> 标签
        cleaned_text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
        if not cleaned_text:
            cleaned_text = text.strip()

        # 2. 尝试直接解析
        try:
            data = json.loads(cleaned_text)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

        # 3. 正则寻找 ```json ... ``` 或 ``` ... ``` 代码块 (从最后一个代码块开始尝试)
        pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        matches = re.findall(pattern, cleaned_text)
        for match in reversed(matches):
            try:
                data = json.loads(match.strip())
                if isinstance(data, dict):
                    return data
            except Exception:
                continue

        # 4. 从后向前倒序检索有效的 { ... } 闭合块 (兼容前面有 CoT 思考散文的场景)
        # 寻找所有以 { 开头并以 } 结尾的候选子串，优先取最后一个
        for m in reversed(list(re.finditer(r"(\{[^{}]*\}|(?<=\n)\{[\s\S]*?\}(?=\n|$))", cleaned_text))):
            candidate = m.group(0).strip()
            try:
                data = json.loads(candidate)
                if isinstance(data, dict):
                    return data
            except Exception:
                continue

        # 5. 兜底尝试寻找最外层大括号
        brace_match = re.search(r"(\{[\s\S]*\})", cleaned_text)
        if brace_match:
            try:
                data = json.loads(brace_match.group(1))
                if isinstance(data, dict):
                    return data
            except Exception:
                pass

        logger.warning("未能从模型输出文本中提取到合规 JSON 块。")
        return None

    @classmethod
    def parse_filter_plan(cls, text: str) -> FilterPlan:
        """解析 NL-to-Filter 输出结果，提供默认安全回退"""
        raw_json = cls.extract_json_block(text)
        if raw_json:
            try:
                return FilterPlan(**raw_json)
            except Exception as e:
                logger.warning("Pydantic 校验 FilterPlan 失败，使用宽松解析: %s", str(e))
                # 宽松解析
                return FilterPlan(
                    explanation=str(raw_json.get("explanation", "自动解析规则")),
                    rules=[
                        FilterRule(field=r.get("field"), operator=r.get("operator", ">="), value=r.get("value"))
                        for r in raw_json.get("rules", []) if isinstance(r, dict) and "field" in r
                    ],
                    sort_by=raw_json.get("sort_by", "change_pct"),
                    sort_ascending=bool(raw_json.get("sort_ascending", False)),
                    limit=int(raw_json.get("limit", 30))
                )
        # 默认备用筛选方案
        return FilterPlan(
            explanation="默认筛选：近期涨幅居前股票",
            rules=[FilterRule(field="change_pct", operator=">=", value=0.0)],
            sort_by="change_pct",
            sort_ascending=False,
            limit=30
        )

    @classmethod
    def parse_recommend_response(cls, text: str) -> RecommendResponse:
        """解析候选池推荐精排结果"""
        raw_json = cls.extract_json_block(text)
        if raw_json:
            try:
                return RecommendResponse(**raw_json)
            except Exception as e:
                logger.warning("校验 RecommendResponse 异常: %s", str(e))
        return RecommendResponse()

output_parser = OutputParser()
