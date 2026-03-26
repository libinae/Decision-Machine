from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class Side(Enum):
    """辩论的正反方"""
    PROS = "pros"      # 正方
    CONS = "cons"      # 反方
    NEUTRAL = "neutral"  # 中立（裁判）

class Phase(Enum):
    """辩论阶段"""
    GROUPING = "grouping"           # 分组阶段
    OPENING = "opening"            # 开篇陈词
    FREE_DEBATE = "free_debate"    # 自由辩论
    CLOSING = "closing"            # 结辩
    RULING = "ruling"              # 裁判裁决

@dataclass
class Persona:
    """人格定义"""
    name: str              # 中文名称，如 "冒险人格"
    icon: str              # emoji 图标，如 "🚀"
    description: str       # 特点描述
    prompt_template: str   # 系统提示词模板
    decision_bias: str     # 决策倾向

@dataclass
class Speech:
    """一次发言"""
    speaker: str           # 发言者名称（带图标）
    content: str           # 发言内容
    side: Side             # 所属阵营
    persona: Persona       # 对应人格
    round: int = 0          # 第几轮
    phase: Phase = Phase.FREE_DEBATE  # 所属阶段
    position: str = "一辩"   # 一辩/二辩/裁判

@dataclass
class Team:
    """辩论队伍"""
    side: Side
    first_debater: Persona  # 一辩
    second_debater: Persona  # 二辩

@dataclass
class GroupingResult:
    pros_team: Team
    cons_team: Team
    judge: Persona
    reason: str = ""


@dataclass
class BackgroundQA:
    """背景问答"""
    questions: list[str]
    answers: list[str]


@dataclass
class DebateResult:
    """辩论最终结果"""
    topic: str
    grouping: GroupingResult
    speeches: list[Speech] = field(default_factory=list)
    judge_ruling: str = ""
    winner: Optional[Side] = None
    grouping_reason: str = ""
    background_qa: BackgroundQA | None = None


__all__ = [
    "Side",
    "Phase",
    "Persona",
    "Speech",
    "Team",
    "GroupingResult",
    "BackgroundQA",
    "DebateResult",
]
