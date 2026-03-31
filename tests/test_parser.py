"""辩题解析测试"""

import sys
from pathlib import Path

# 添加 src 目录到路径
project_root = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(project_root))

# 导入 CLI 模块的解析函数
cli_path = Path(__file__).resolve().parents[1] / "cli"
sys.path.insert(0, str(cli_path))

from main import parse_debate_topic


class TestParseDebateTopic:
    """测试辩题解析功能"""

    def test_parse_with_haishi(self):
        """测试使用'还是'分隔的辩题"""
        topic = "我应该辞职创业还是继续上班？"
        pros, cons = parse_debate_topic(topic)
        assert pros == "辞职创业"
        assert cons == "继续上班"

    def test_parse_with_vs(self):
        """测试使用'vs'分隔的辩题"""
        topic = "我应该买房 vs 租房"
        pros, cons = parse_debate_topic(topic)
        assert pros == "买房"
        assert cons == "租房"

    def test_parse_with_or(self):
        """测试使用'或者'分隔的辩题"""
        topic = "我应该去大城市或者留在老家"
        pros, cons = parse_debate_topic(topic)
        assert pros == "去大城市"
        assert cons == "留在老家"

    def test_parse_with_colon(self):
        """测试使用冒号分隔的辩题"""
        topic = "我应该接受这份工作：继续寻找更好的机会"
        pros, cons = parse_debate_topic(topic)
        assert pros == "接受这份工作"
        assert cons == "继续寻找更好的机会"

    def test_parse_with_question_mark(self):
        """测试使用问号分隔的辩题"""
        topic = "辞职创业？继续上班"
        pros, cons = parse_debate_topic(topic)
        assert pros == "辞职创业"
        assert cons == "继续上班"

    def test_parse_fallback(self):
        """测试无法解析时的默认处理"""
        topic = "我应该做一件事"
        pros, cons = parse_debate_topic(topic)
        assert pros == "做一件事"
        assert cons == "不做一件事"

    def test_parse_with_prefix_variations(self):
        """测试不同前缀的处理"""
        topics = [
            ("我应该辞职创业还是继续上班", "辞职创业", "继续上班"),
            ("我要辞职创业还是继续上班", "辞职创业", "继续上班"),
        ]
        for topic, expected_pros, expected_cons in topics:
            pros, cons = parse_debate_topic(topic)
            assert pros == expected_pros
            assert cons == expected_cons
