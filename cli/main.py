#!/usr/bin/env python3
"""多人格决策机 - 命令行入口"""

import asyncio
import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(project_root))


def get_input_with_default(prompt: str, default: str = "") -> str:
    """获取用户输入，支持默认值"""
    if default:
        response = input(f"{prompt} [{default}]: ").strip()
        return response if response else default
    return input(f"{prompt}: ").strip()


async def run_debate():
    """基于交互输入启动辩论引擎"""
    print("🎯 多重人格决策机")
    print("=" * 50)
    print()

    api_key = os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        print("⚠️  DASHSCOPE_API_KEY 未设置，可能影响部分功能")
        print()

    # 获取辩题
    topic = get_input_with_default(
        "请输入决策主题",
        "我应该辞职创业还是继续上班？",
    )
    if not topic:
        print("❌ 辩题不能为空")
        return 1

    # 简单文本解析出正反方
    pros_position: str
    cons_position: str
    if "？" in topic:
        parts = topic.replace("？", "?").split("?")
        pros_position = parts[0].strip() or topic
        cons_position = parts[1].strip() if len(parts) > 1 else "不" + pros_position
    elif "还是" in topic:
        parts = topic.split("还是")
        pros_position = parts[0].replace("我应该", "").strip()
        cons_position = parts[1].strip() if len(parts) > 1 else "不" + pros_position
    else:
        pros_position = topic
        cons_position = "不" + topic

    print()
    print(f"正方立场：{pros_position}")
    print(f"反方立场：{cons_position}")
    print()

    confirm = get_input_with_default("确认开始辩论？", "Y")
    if confirm.lower() not in ["y", "是", "确认", ""]:
        print("已取消")
        return 0

    print()
    print("🤖 正在初始化辩论系统...")
    print()

    
    try:
        from decision_machine.engine import DebateEngine
        from decision_machine.config import AppConfig
    except Exception as e:
        print(f"初始化失败：{e}")
        return 2

    config = AppConfig.from_env()
    engine = DebateEngine(
        topic=topic,
        pros_position=pros_position,
        cons_position=cons_position,
        config=config,
    )

    try:
        result = await engine.run()
        print("✅ 辩论完成！")
        if result.winner is not None:
            winner_side = "正方" if result.winner == __import__('decision_machine.types').types.Side.PROS else "反方"
            print(f"裁定胜方：{winner_side}")
        else:
            print("裁定结果：平局")
        return 0
    except Exception as e:
        print(f"❌ 辩论过程中出错：{e}")
        import traceback
        traceback.print_exc()
        return 3


def entry_point():
    """CLI 入口，外部直接调用时执行 asyncio 运行"""
    code = asyncio.run(run_debate())
    return code


if __name__ == "__main__":  # 直接执行脚本运行
    sys.exit(entry_point())
