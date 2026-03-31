from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class ModelConfig:
    model_name: str = "qwen3.5-plus"
    api_key: str = ""

    @classmethod
    def from_env(cls) -> ModelConfig:
        api_key = os.environ.get("DASHSCOPE_API_KEY", "")
        model_name = os.environ.get("DM_MODEL_NAME", "qwen3.5-plus")
        return cls(api_key=api_key, model_name=model_name)


@dataclass
class DebateConfig:
    max_debate_rounds: int = 10
    max_total_rounds: int = 20
    early_stop_at: int = 10


@dataclass
class AppConfig:
    model: ModelConfig = field(default_factory=ModelConfig.from_env)
    debate: DebateConfig = field(default_factory=DebateConfig)

    @classmethod
    def from_env(cls) -> AppConfig:
        return cls(
            model=ModelConfig.from_env(),
            debate=DebateConfig(max_debate_rounds=int(os.getenv("DECISION_MAX_ROUNDS", "10"))),
        )
