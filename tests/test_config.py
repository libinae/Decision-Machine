"""配置测试"""

import os
import sys
from pathlib import Path

# 添加 src 目录到路径
project_root = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(project_root))

from decision_machine.config import AppConfig, DebateConfig, ModelConfig


class TestModelConfig:
    """测试 ModelConfig"""

    def test_model_config_defaults(self):
        """测试默认值"""
        config = ModelConfig()
        assert config.model_name == "qwen3.5-plus"
        assert config.api_key == ""

    def test_model_config_from_env(self):
        """测试从环境变量加载"""
        # 设置临时环境变量
        os.environ["DASHSCOPE_API_KEY"] = "test-api-key"
        os.environ["DM_MODEL_NAME"] = "test-model"

        config = ModelConfig.from_env()
        assert config.api_key == "test-api-key"
        assert config.model_name == "test-model"

        # 清理环境变量
        del os.environ["DASHSCOPE_API_KEY"]
        del os.environ["DM_MODEL_NAME"]

    def test_model_config_from_env_defaults(self):
        """测试环境变量缺失时的默认值"""
        # 确保环境变量不存在
        if "DASHSCOPE_API_KEY" in os.environ:
            del os.environ["DASHSCOPE_API_KEY"]
        if "DM_MODEL_NAME" in os.environ:
            del os.environ["DM_MODEL_NAME"]

        config = ModelConfig.from_env()
        assert config.api_key == ""
        assert config.model_name == "qwen3.5-plus"


class TestDebateConfig:
    """测试 DebateConfig"""

    def test_debate_config_defaults(self):
        """测试默认值"""
        config = DebateConfig()
        assert config.max_debate_rounds == 10
        assert config.max_total_rounds == 20
        assert config.early_stop_at == 10


class TestAppConfig:
    """测试 AppConfig"""

    def test_app_config_from_env(self):
        """测试从环境变量加载"""
        # 设置临时环境变量
        os.environ["DASHSCOPE_API_KEY"] = "test-api-key"
        os.environ["DECISION_MAX_ROUNDS"] = "15"

        config = AppConfig.from_env()
        assert config.model.api_key == "test-api-key"
        assert config.debate.max_debate_rounds == 15

        # 清理环境变量
        del os.environ["DASHSCOPE_API_KEY"]
        del os.environ["DECISION_MAX_ROUNDS"]

    def test_app_config_defaults(self):
        """测试默认值"""
        if "DASHSCOPE_API_KEY" in os.environ:
            del os.environ["DASHSCOPE_API_KEY"]
        if "DECISION_MAX_ROUNDS" in os.environ:
            del os.environ["DECISION_MAX_ROUNDS"]

        config = AppConfig.from_env()
        assert config.debate.max_debate_rounds == 10
