import unicodedata
from typing import Generator, Optional
from ..types import Side, Persona, Speech, GroupingResult, Phase


_SIDE_COLORS = {
    Side.PROS: "\033[36m",
    Side.CONS: "\033[35m",
    None: "\033[0m",
}
_SIDE_RESET = "\033[0m"


def visual_width(text: str) -> int:
    """计算字符串在终端的视觉宽度（中文字符和emoji算2个宽度）"""
    width = 0
    for char in text:
        if unicodedata.east_asian_width(char) in ('F', 'W'):  # Full-width
            width += 2
        else:
            width += 1
    return width


def center_align(text: str, width: int) -> str:
    """将文本居中对齐到指定宽度（正确处理中文字符和emoji）"""
    text_width = visual_width(text)
    padding = width - text_width
    left = padding // 2
    right = padding - left
    return " " * left + text + " " * right


def left_align(text: str, width: int) -> str:
    """将文本左对齐到指定宽度（正确处理中文字符和emoji）"""
    text_width = visual_width(text)
    padding = width - text_width
    return text + " " * padding


class TerminalUI:

    def clear_line(self) -> str:
        return "\033[2K\r"

    def print_header(self, topic: str) -> None:
        width = 60
        print()
        print("╔" + "═" * width + "╗")
        print(f"║{center_align('🎯 多人格决策', width)}║")
        print(f"║{center_align('', width)}║")
        topic_line = f"决策主题：{topic}"
        print(f"║ {topic_line}{' ' * (width - 1 - visual_width(topic_line))} ║")
        print("╚" + "═" * width + "╝")
        print()

    def print_persona_init(self, persona: Persona, success: bool = True) -> None:
        status = "✓" if success else "✗"
        print(f"    {persona.icon} {persona.name}  {status}")

    def print_phase(self, phase_name: str) -> None:
        width = 50
        print()
        print("╟" + "─" * width + "╢")
        print(f"  📋 {phase_name}")
        print("╟" + "─" * width + "╢")
        print()

    def _get_pros_position(self) -> str:
        return getattr(self, '_pros_position', '正方')

    def _get_cons_position(self) -> str:
        return getattr(self, '_cons_position', '反方')

    def set_positions(self, pros: str, cons: str) -> None:
        self._pros_position = pros
        self._cons_position = cons

    def print_stance(self, speaker: str, content: str, persona_name: str) -> None:
        print(f"    {speaker} {persona_name}：")
        print(f"    {content}")
        print()

    def print_grouping_result(self, grouping: GroupingResult) -> None:
        print("      ○ 正方：" + self._get_pros_position())
        print("      ● 反方：" + self._get_cons_position())
        print()
        print("  " + "━" * 50)
        print("    分组结果")
        print(f"      ○ 正方一辩 → {grouping.pros_team.first_debater.icon} {grouping.pros_team.first_debater.name}")
        print(f"      ○ 正方二辩 → {grouping.pros_team.second_debater.icon} {grouping.pros_team.second_debater.name}")
        print(f"      ● 反方一辩 → {grouping.cons_team.first_debater.icon} {grouping.cons_team.first_debater.name}")
        print(f"      ● 反方二辩 → {grouping.cons_team.second_debater.icon} {grouping.cons_team.second_debater.name}")
        print(f"      ⚖️ 裁判 → {grouping.judge.icon} {grouping.judge.name}")
        print("  " + "━" * 50)
        print()

    def print_grouping_reason(self, reason: str) -> None:
        print("  " + "━" * 50)
        print("    分组理由")
        print(f"  {reason}")
        print("  " + "━" * 50)
        print()

    def print_qa_intro(self) -> None:
        print("  为帮助辩手更深入理解你的情况，裁判将提出 5 个背景问题。")
        print("  请如实作答（直接回车跳过）：")
        print()

    def print_qa_question(self, q_num: int, question: str) -> str:
        answer = input(f"  【问题{q_num}】{question}\n  你的回答：").strip()
        return answer

    def _wrap_pros(self, text: str) -> str:
        return f"{_SIDE_COLORS[Side.PROS]}{text}{_SIDE_RESET}"

    def _wrap_cons(self, text: str) -> str:
        return f"{_SIDE_COLORS[Side.CONS]}{text}{_SIDE_RESET}"

    def print_speech(
        self,
        speaker: str,
        content: str,
        side: Side,
        phase: Optional[Phase] = None,
        step: Optional[int] = None
    ) -> None:
        prefix = ""
        if step:
            side_indicator = "○" if side == Side.PROS else "●"
            prefix = f"  {side_indicator} 第{step}步："
        elif phase:
            prefix = f"  ⚖️ "

        print(prefix + speaker + " 发言：")
        print("    " + "─" * 25)

        if side == Side.PROS:
            print(f"    {self._wrap_pros(content)}")
        elif side == Side.CONS:
            print(f"    {self._wrap_cons(content)}")
        else:
            print(f"    {content}")

        print()

    def stream_speech(
        self,
        speaker: str,
        content: str,
        side: Side,
        phase: Optional[Phase] = None,
        step: Optional[int] = None,
    ) -> str:
        prefix = ""
        if step:
            side_indicator = "○" if side == Side.PROS else "●"
            prefix = f"  {side_indicator} 第{step}步："
        elif phase:
            prefix = f"  ⚖️ "

        print(prefix + speaker + " 发言：")
        print("    " + "─" * 25)
        color = _SIDE_COLORS.get(side, "")
        print(f"    {color}{content}{_SIDE_RESET}")
        print()
        return content

    def print_judge_ruling(self, ruling: str) -> None:
        print("  ⚖️ 裁判总结：")
        print("    " + "─" * 25)
        print(f"    {ruling}")
        print()

    def print_winner(self, winner: Optional[Side]) -> None:
        width = 50
        print()
        print("╔" + "═" * width + "╗")

        if winner == Side.PROS:
            result = "🏆 裁决结果：正方胜出！"
        elif winner == Side.CONS:
            result = "🏆 裁决结果：反方胜出！"
        else:
            result = "🤝 裁决结果：平局！"

        print(f"║{center_align(result, width)}║")
        print("╚" + "═" * width + "╝")
        print()
