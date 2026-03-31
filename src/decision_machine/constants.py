"""多人格决策机常量定义

统一管理项目中的魔法字符串和配置常量
"""

# 人格名称常量
PERSONA_RISK_TAKER = "冒险人格"
PERSONA_CONSERVATIVE = "保守人格"
PERSONA_EMPATHETIC = "感性人格"
PERSONA_RATIONAL = "理性人格"
PERSONA_SYNTHESIZER = "综合人格"

# 裁判人格名称
JUDGE_PERSONA_NAME = PERSONA_SYNTHESIZER

# 所有人格名称列表
ALL_PERSONA_NAMES = [
    PERSONA_RISK_TAKER,
    PERSONA_CONSERVATIVE,
    PERSONA_EMPATHETIC,
    PERSONA_RATIONAL,
    PERSONA_SYNTHESIZER,
]

# 辩手人格名称列表（不含裁判）
DEBATER_PERSONA_NAMES = [
    PERSONA_RISK_TAKER,
    PERSONA_CONSERVATIVE,
    PERSONA_EMPATHETIC,
    PERSONA_RATIONAL,
]

# 辩论配置常量
DEFAULT_MAX_ROUNDS = 10
DEFAULT_EARLY_STOP = 10
MAX_CONTEXT_SPEECHES = 15  # 上下文窗口限制，防止超出 token

# 背景问答配置
DEFAULT_BACKGROUND_QUESTIONS = [
    "你目前的年龄和所处的人生阶段是什么？",
    "你的经济状况如何？有没有足够的储蓄或收入来源？",
    "你的家庭情况是怎样的？有没有需要照顾的人？",
    "你目前的工作经验和能力积累到什么程度？",
    "你内心最大的顾虑或障碍是什么？",
]

# 输出格式常量
TERMINAL_WIDTH = 60
PHASE_SEPARATOR_WIDTH = 50

# 裁决关键词
RULING_KEYWORDS = {
    "pros_win": "正方胜",
    "cons_win": "反方胜",
    "draw": ["平局", "和局"],
}

# 分组关键词
GROUPING_KEYWORDS = {
    "pros": ["支持正方", "赞成", "应该", "选择", "正方"],
    "cons": ["支持反方", "反对", "不应该", "反方"],
}


__all__ = [
    "PERSONA_RISK_TAKER",
    "PERSONA_CONSERVATIVE",
    "PERSONA_EMPATHETIC",
    "PERSONA_RATIONAL",
    "PERSONA_SYNTHESIZER",
    "JUDGE_PERSONA_NAME",
    "ALL_PERSONA_NAMES",
    "DEBATER_PERSONA_NAMES",
    "DEFAULT_MAX_ROUNDS",
    "DEFAULT_EARLY_STOP",
    "MAX_CONTEXT_SPEECHES",
    "DEFAULT_BACKGROUND_QUESTIONS",
    "TERMINAL_WIDTH",
    "PHASE_SEPARATOR_WIDTH",
    "RULING_KEYWORDS",
    "GROUPING_KEYWORDS",
]
