"""分组逻辑测试"""

import sys
from pathlib import Path

# 添加 src 目录到路径
project_root = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(project_root))

from decision_machine.constants import GROUPING_KEYWORDS, JUDGE_PERSONA_NAME


class TestInferSide:
    """测试立场推断逻辑"""

    def test_infer_pros_with_keywords(self):
        """测试正方关键词识别"""
        content = "我认为应该选择这个方案，支持正方观点"
        pros_keywords = GROUPING_KEYWORDS["pros"]
        cons_keywords = GROUPING_KEYWORDS["cons"]
        pros_count = sum(1 for kw in pros_keywords if kw in content)
        cons_count = sum(1 for kw in cons_keywords if kw in content)
        assert pros_count > cons_count

    def test_infer_cons_with_keywords(self):
        """测试反方关键词识别"""
        content = "我反对这个想法，支持反方立场，不应该这样做"
        pros_keywords = GROUPING_KEYWORDS["pros"]
        cons_keywords = GROUPING_KEYWORDS["cons"]
        pros_count = sum(1 for kw in pros_keywords if kw in content)
        cons_count = sum(1 for kw in cons_keywords if kw in content)
        assert cons_count > pros_count

    def test_infer_neutral(self):
        """测试中立情况"""
        content = "我持中立态度，两边都有道理"
        pros_keywords = GROUPING_KEYWORDS["pros"]
        cons_keywords = GROUPING_KEYWORDS["cons"]
        pros_count = sum(1 for kw in pros_keywords if kw in content)
        cons_count = sum(1 for kw in cons_keywords if kw in content)
        assert pros_count == cons_count


class TestConstants:
    """测试常量在分组中的使用"""

    def test_judge_persona_name(self):
        """测试裁判人格名称"""
        assert JUDGE_PERSONA_NAME == "综合人格"

    def test_grouping_keywords_structure(self):
        """测试分组关键词结构"""
        assert "pros" in GROUPING_KEYWORDS
        assert "cons" in GROUPING_KEYWORDS
        assert isinstance(GROUPING_KEYWORDS["pros"], list)
        assert isinstance(GROUPING_KEYWORDS["cons"], list)


class TestPersonaMatching:
    """测试人格匹配"""

    def test_find_persona_by_name(self):
        """测试按名称查找人格"""
        from decision_machine.agents import PERSONAS

        # 查找裁判人格
        judge = next(p for p in PERSONAS if p.name == JUDGE_PERSONA_NAME)
        assert judge.name == "综合人格"

        # 查找辩手人格
        debaters = [p for p in PERSONAS if p.name != JUDGE_PERSONA_NAME]
        assert len(debaters) == 4
