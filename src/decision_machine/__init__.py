"""
多人格决策机

基于 AgentScope 的多智能体辩论式决策辅助工具
"""

from .agents import PERSONAS, AgentFactory
from .config import AppConfig, DebateConfig, ModelConfig
from .constants import (
    DEBATER_PERSONA_NAMES,
    GROUPING_KEYWORDS,
    JUDGE_PERSONA_NAME,
    MAX_CONTEXT_SPEECHES,
    RULING_KEYWORDS,
)
from .engine import DebateEngine, DebatePhases, GroupingEngine
from .types import (
    DebateResult,
    DebateSetup,
    GroupingResult,
    Persona,
    Phase,
    Side,
    Speech,
    Team,
    TeamAgents,
)

__all__ = [
    # Types
    "Side",
    "Phase",
    "Persona",
    "Speech",
    "Team",
    "GroupingResult",
    "DebateResult",
    "TeamAgents",
    "DebateSetup",
    # Config
    "AppConfig",
    "DebateConfig",
    "ModelConfig",
    # Constants
    "JUDGE_PERSONA_NAME",
    "DEBATER_PERSONA_NAMES",
    "MAX_CONTEXT_SPEECHES",
    "GROUPING_KEYWORDS",
    "RULING_KEYWORDS",
    # Agents
    "AgentFactory",
    "PERSONAS",
    # Engine
    "DebateEngine",
    "DebatePhases",
    "GroupingEngine",
]
