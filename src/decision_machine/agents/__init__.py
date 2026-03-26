"""决策机器-代理（Agent）模块入口

- 暴露 five大人格定义与工厂接口
"""

from .personas import (
    PERSONAS,
    RISK_TAKER,
    CONSERVATIVE,
    EMPATHETIC,
    RATIONAL,
    SYNTHESIZER,
)
from .factory import AgentFactory

__all__ = [
    "PERSONAS",
    "RISK_TAKER",
    "CONSERVATIVE",
    "EMPATHETIC",
    "RATIONAL",
    "SYNTHESIZER",
    "AgentFactory",
]
