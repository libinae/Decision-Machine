"""
多人格决策机

基于 AgentScope 的多智能体辩论式决策辅助工具
"""

from .types import Side, Phase, Persona, Speech, Team, GroupingResult, DebateResult
from .config import AppConfig, DebateConfig, ModelConfig
from .agents import AgentFactory, PERSONAS
from .engine import DebateEngine, DebatePhases, GroupingEngine

__all__ = [
    # Types
    "Side",
    "Phase",
    "Persona",
    "Speech",
    "Team",
    "GroupingResult",
    "DebateResult",
    # Config
    "AppConfig",
    "DebateConfig",
    "ModelConfig",
    # Agents
    "AgentFactory",
    "PERSONAS",
    # Engine
    "DebateEngine",
    "DebatePhases",
    "GroupingEngine",
]
