#!/usr/bin/env python3
"""测试辩论系统"""
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch

project_root = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(project_root))

MOCK_ANSWERS = [
    "30岁，资深软件工程师，有一定积蓄",
    "有约40万存款，房贷已还清，无其他负债",
    "已婚，有一个3岁孩子，父母有退休金",
    "在互联网大厂工作8年，做过后端和前端，创业方向是SaaS工具",
    "最大顾虑是家庭经济压力大，但内心渴望创造自己的产品",
]


async def test_debate():
    from decision_machine.engine import DebateEngine
    from decision_machine.config import AppConfig

    topic = "我应该辞职创业还是继续上班？"
    pros_position = "辞职创业"
    cons_position = "继续上班"

    answer_iter = iter(MOCK_ANSWERS)

    def mock_input(prompt):
        try:
            answer = next(answer_iter)
            print(f"  你的回答：{answer}")
            return answer
        except StopIteration:
            return ""

    with patch("builtins.input", mock_input):
        config = AppConfig.from_env()
        engine = DebateEngine(
            topic=topic,
            pros_position=pros_position,
            cons_position=cons_position,
            config=config,
        )
        result = await engine.run()

    print("✅ 辩论完成！")
    if result.winner is not None:
        from decision_machine.types import Side
        winner_side = "正方" if result.winner == Side.PROS else "反方"
        print(f"裁定胜方：{winner_side}")
    else:
        print("裁定结果：平局")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(test_debate()))
