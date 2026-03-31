"""辩论结果导出模块

支持将辩论结果导出为 Markdown 格式的报告
"""

from datetime import datetime
from pathlib import Path

from .types import DebateResult, Phase, Side


def format_markdown(result: DebateResult) -> str:
    """将辩论结果格式化为 Markdown 报告

    Args:
        result: DebateResult 实例

    Returns:
        Markdown 格式的字符串
    """
    lines = []

    # 标题
    lines.append("# 🎯 多人格决策机 - 辩论报告")
    lines.append("")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # 辩题信息
    lines.append("## 📋 辩题信息")
    lines.append("")
    lines.append(f"- **决策主题**: {result.topic}")
    lines.append(f"- **分组理由**: {result.grouping_reason}")
    lines.append("")

    # 分组结果
    lines.append("## 🎭 分组结果")
    lines.append("")
    lines.append("### 正方队伍")
    lines.append(
        f"- **一辩**: {result.grouping.pros_team.first_debater.icon} {result.grouping.pros_team.first_debater.name}"
    )
    lines.append(
        f"- **二辩**: {result.grouping.pros_team.second_debater.icon} {result.grouping.pros_team.second_debater.name}"
    )
    lines.append("")
    lines.append("### 反方队伍")
    lines.append(
        f"- **一辩**: {result.grouping.cons_team.first_debater.icon} {result.grouping.cons_team.first_debater.name}"
    )
    lines.append(
        f"- **二辩**: {result.grouping.cons_team.second_debater.icon} {result.grouping.cons_team.second_debater.name}"
    )
    lines.append("")
    lines.append(f"- **裁判**: {result.grouping.judge.icon} {result.grouping.judge.name}")
    lines.append("")

    # 背景信息
    if result.background_qa:
        lines.append("## 📝 用户背景信息")
        lines.append("")
        for i, (q, a) in enumerate(
            zip(result.background_qa.questions, result.background_qa.answers), 1
        ):
            lines.append(f"**问题 {i}**: {q}")
            lines.append(f"- **回答**: {a}")
            lines.append("")

    # 辩论过程
    lines.append("## 💬 辩论过程")
    lines.append("")

    phase_names = {
        Phase.GROUPING: "讨论与分组",
        Phase.OPENING: "开篇陈词",
        Phase.FREE_DEBATE: "自由辩论",
        Phase.CLOSING: "结辩",
    }

    current_phase = None
    for speech in result.speeches:
        if speech.phase != current_phase:
            current_phase = speech.phase
            phase_name = phase_names.get(current_phase, "辩论")
            lines.append(f"### {phase_name}")
            lines.append("")

        side_indicator = "○" if speech.side == Side.PROS else "●"
        side_name = (
            "正方" if speech.side == Side.PROS else "反方" if speech.side == Side.CONS else "中立"
        )
        lines.append(f"**{side_indicator} [{side_name} {speech.position}] {speech.speaker}**")
        lines.append("")
        lines.append(f"{speech.content}")
        lines.append("")

    # 裁决结果
    lines.append("## ⚖️ 裁判裁决")
    lines.append("")
    lines.append(result.judge_ruling)
    lines.append("")

    # 最终结果
    lines.append("## 🏆 最终结果")
    lines.append("")
    if result.winner == Side.PROS:
        lines.append("**裁决: 正方胜出**")
    elif result.winner == Side.CONS:
        lines.append("**裁决: 反方胜出**")
    else:
        lines.append("**裁决: 平局**")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*本报告由多人格决策机自动生成*")

    return "\n".join(lines)


def save_to_file(result: DebateResult, filepath: Path | str) -> None:
    """将辩论结果保存为 Markdown 文件

    Args:
        result: DebateResult 实例
        filepath: 目标文件路径
    """
    file_path = Path(filepath)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    content = format_markdown(result)
    file_path.write_text(content, encoding="utf-8")


def generate_filename(result: DebateResult) -> str:
    """生成默认的文件名

    Args:
        result: DebateResult 实例

    Returns:
        文件名（不含扩展名）
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # 从辩题中提取关键词作为文件名
    topic_short = (
        result.topic.replace("我应该", "")
        .replace("还是", "_")
        .replace("？", "")
        .replace("?", "")[:30]
    )
    return f"debate_{timestamp}_{topic_short}.md"


__all__ = ["format_markdown", "save_to_file", "generate_filename"]
