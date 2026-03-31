"""类型和数据类测试"""

import sys
from pathlib import Path

# 添加 src 目录到路径
project_root = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(project_root))

from decision_machine.types import (
    DebateResult,
    GroupingResult,
    Persona,
    Phase,
    Side,
    Speech,
    Team,
)


class TestSide:
    """测试 Side 枚举"""

    def test_side_values(self):
        """测试枚举值"""
        assert Side.PROS.value == "pros"
        assert Side.CONS.value == "cons"
        assert Side.NEUTRAL.value == "neutral"

    def test_side_comparison(self):
        """测试枚举比较"""
        assert Side.PROS != Side.CONS
        assert Side.PROS == Side.PROS


class TestPhase:
    """测试 Phase 枚举"""

    def test_phase_values(self):
        """测试枚举值"""
        assert Phase.GROUPING.value == "grouping"
        assert Phase.OPENING.value == "opening"
        assert Phase.FREE_DEBATE.value == "free_debate"
        assert Phase.CLOSING.value == "closing"
        assert Phase.RULING.value == "ruling"


class TestPersona:
    """测试 Persona 数据类"""

    def test_persona_creation(self):
        """测试创建 Persona"""
        persona = Persona(
            name="测试人格",
            icon="🧪",
            description="这是一个测试人格",
            prompt_template="测试模板",
            decision_bias="测试倾向",
        )
        assert persona.name == "测试人格"
        assert persona.icon == "🧪"


class TestSpeech:
    """测试 Speech 数据类"""

    def test_speech_creation(self):
        """测试创建 Speech"""
        persona = Persona(
            name="测试人格",
            icon="🧪",
            description="测试",
            prompt_template="测试",
            decision_bias="测试",
        )
        speech = Speech(
            speaker="🧪 测试人格",
            content="这是发言内容",
            side=Side.PROS,
            persona=persona,
            round=1,
            phase=Phase.FREE_DEBATE,
            position="一辩",
        )
        assert speech.speaker == "🧪 测试人格"
        assert speech.side == Side.PROS
        assert speech.round == 1


class TestTeam:
    """测试 Team 数据类"""

    def test_team_creation(self):
        """测试创建 Team"""
        persona1 = Persona(
            name="人格1",
            icon="1️⃣",
            description="测试",
            prompt_template="测试",
            decision_bias="测试",
        )
        persona2 = Persona(
            name="人格2",
            icon="2️⃣",
            description="测试",
            prompt_template="测试",
            decision_bias="测试",
        )
        team = Team(
            side=Side.PROS,
            first_debater=persona1,
            second_debater=persona2,
        )
        assert team.side == Side.PROS
        assert team.first_debater.name == "人格1"


class TestDebateResult:
    """测试 DebateResult 数据类"""

    def test_debate_result_creation(self):
        """测试创建 DebateResult"""
        persona1 = Persona(
            name="人格1",
            icon="1️⃣",
            description="测试",
            prompt_template="测试",
            decision_bias="测试",
        )
        persona2 = Persona(
            name="人格2",
            icon="2️⃣",
            description="测试",
            prompt_template="测试",
            decision_bias="测试",
        )
        judge = Persona(
            name="裁判",
            icon="⚖️",
            description="测试",
            prompt_template="测试",
            decision_bias="测试",
        )

        pros_team = Team(side=Side.PROS, first_debater=persona1, second_debater=persona2)
        cons_team = Team(side=Side.CONS, first_debater=persona2, second_debater=persona1)
        grouping = GroupingResult(pros_team=pros_team, cons_team=cons_team, judge=judge)

        result = DebateResult(
            topic="测试辩题",
            grouping=grouping,
        )
        assert result.topic == "测试辩题"
        assert result.speeches == []
        assert result.winner is None


class TestConstants:
    """测试常量定义"""

    def test_constants_import(self):
        """测试常量可以正确导入"""
        from decision_machine.constants import (
            DEBATER_PERSONA_NAMES,
            JUDGE_PERSONA_NAME,
            MAX_CONTEXT_SPEECHES,
        )
        assert JUDGE_PERSONA_NAME == "综合人格"
        assert MAX_CONTEXT_SPEECHES == 15
        assert len(DEBATER_PERSONA_NAMES) == 4
