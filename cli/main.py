#!/usr/bin/env python3
"""多人格决策机 - 命令行入口"""

import asyncio
import os
import re
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


def parse_debate_topic(topic: str) -> tuple[str, str]:
    """解析辩题，提取正方和反方立场

    支持多种格式：
    - "我应该A还是B？" - 使用"还是"分隔
    - "我应该A vs B" - 使用"vs"分隔
    - "我应该A versus B" - 使用"versus"分隔
    - "我应该A或者B" - 使用"或者"分隔
    - "我应该A:B" - 使用冒号分隔

    Args:
        topic: 用户输入的辩题

    Returns:
        (正方立场, 反方立场)
    """
    pros_position: str
    cons_position: str

    # 移除常见的开头前缀
    clean_topic = topic.replace("我应该", "").replace("我要", "").replace("我", "").strip()

    # 尝试多种分隔符来解析辩题
    separators = ["还是", " vs ", " VS ", " versus ", "或者", "或"]

    for sep in separators:
        if sep in clean_topic:
            parts = clean_topic.split(sep)
            pros_position = parts[0].strip().replace("？", "").replace("?", "")
            cons_position = (
                parts[1].strip().replace("？", "").replace("?", "")
                if len(parts) > 1
                else f"不{pros_position}"
            )
            return pros_position, cons_position

    # 尝试匹配中英文问号
    match = re.match(r"^(.+?)[？?]+(.+?)[？?]*$", clean_topic)
    if match:
        pros_position = match.group(1).strip()
        cons_position = match.group(2).strip()
        return pros_position, cons_position

    # 尝试冒号分隔
    if ":" in clean_topic or "：" in clean_topic:
        sep = ":" if ":" in clean_topic else "："
        parts = clean_topic.split(sep)
        pros_position = parts[0].strip()
        cons_position = parts[1].strip() if len(parts) > 1 else f"不{pros_position}"
        return pros_position, cons_position

    # 无法解析时，生成默认反方
    pros_position = clean_topic
    cons_position = f"不{clean_topic}"
    return pros_position, cons_position


async def run_debate():
    """基于交互输入启动辩论引擎"""
    print("🎯 多重人格决策机")
    print("=" * 50)
    print()

    api_key = os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        print("❌ 错误：DASHSCOPE_API_KEY 未设置")
        print("请在 .env 文件中配置或设置环境变量：")
        print("  export DASHSCOPE_API_KEY=\"your-api-key\"")
        print()
        return 1

    # 获取辩题（不再预解析正反方，由 AI 智能分析）
    topic = get_input_with_default(
        "请输入决策主题",
        "我应该辞职创业还是继续上班？",
    )
    if not topic:
        print("❌ 辩题不能为空")
        return 1

    print()
    print("🤖 正在初始化辩论系统...")
    print()

    try:
        from decision_machine.config import AppConfig
        from decision_machine.engine import DebateEngine
    except Exception as e:
        print(f"初始化失败：{e}")
        return 2

    config = AppConfig.from_env()
    engine = DebateEngine(
        topic=topic,
        config=config,
    )

    try:
        result = await engine.run()
        print("✅ 辩论完成！")
        if result.winner is not None:
            winner_side = (
                "正方"
                if result.winner == __import__("decision_machine.types").types.Side.PROS
                else "反方"
            )
            print(f"裁定胜方：{winner_side}")
        else:
            print("裁定结果：平局")
        print()

        # 询问是否保存结果
        save_choice = get_input_with_default("是否保存辩论报告？", "Y")
        if save_choice.lower() in ["y", "是", "保存", ""]:
            from decision_machine.export import generate_filename, save_to_file

            # 生成输出目录和文件名
            output_dir = Path(__file__).resolve().parents[1] / "reports"
            filename = generate_filename(result)
            filepath = output_dir / filename

            save_to_file(result, filepath)
            print(f"📄 报告已保存至: {filepath}")

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
