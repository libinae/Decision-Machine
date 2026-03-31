"""Web UI 适配器 - 替代 TerminalUI，通过 WebSocket 发送消息"""

import sys
from pathlib import Path
from typing import Any

from fastapi import WebSocket

# 添加 src 到路径
project_root = Path(__file__).resolve().parents[3] / "src"
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from decision_machine.types import GroupingResult, Persona, Side


class WebUI:
    """Web 版 UI 适配器，通过 WebSocket 实时发送辩论信息"""

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self._pros_position = "正方"
        self._cons_position = "反方"

    async def _send(self, msg_type: str, data: Any) -> None:
        """发送 WebSocket 消息"""
        await self.websocket.send_json({"type": msg_type, "data": data})

    async def print_header(self, topic: str) -> None:
        """发送标题"""
        await self._send("header", {"topic": topic})

    async def print_persona_init(self, persona: Persona, success: bool = True) -> None:
        """发送人格初始化状态"""
        await self._send("persona_init", {"name": persona.name, "icon": persona.icon, "success": success})

    async def print_phase(self, phase_name: str) -> None:
        """发送阶段切换"""
        await self._send("phase", {"name": phase_name})

    def set_positions(self, pros: str, cons: str) -> None:
        """设置正反方立场"""
        self._pros_position = pros
        self._cons_position = cons

    async def print_grouping_result(self, grouping: GroupingResult) -> None:
        """发送分组结果"""
        await self._send(
            "grouping",
            {
                "pros_position": grouping.pros_position,
                "cons_position": grouping.cons_position,
                "pros_team": {
                    "first": {"name": grouping.pros_team.first_debater.name, "icon": grouping.pros_team.first_debater.icon},
                    "second": {"name": grouping.pros_team.second_debater.name, "icon": grouping.pros_team.second_debater.icon},
                },
                "cons_team": {
                    "first": {"name": grouping.cons_team.first_debater.name, "icon": grouping.cons_team.first_debater.icon},
                    "second": {"name": grouping.cons_team.second_debater.name, "icon": grouping.cons_team.second_debater.icon},
                },
                "judge": {"name": grouping.judge.name, "icon": grouping.judge.icon},
            },
        )

    async def print_qa_intro(self) -> None:
        """发送问答介绍"""
        await self._send("qa_intro", {})

    async def print_qa_question(self, q_num: int, question: str) -> str:
        """发送问题并等待回答"""
        await self._send("qa_question", {"num": q_num, "question": question})
        # 等待用户回答
        data = await self.websocket.receive_json()
        return data.get("answer", "（未回答）")

    async def stream_speech(self, speaker: str, content: str, side: Side) -> str:
        """发送完整发言"""
        await self._send("speech", {"speaker": speaker, "content": content, "side": side.value})
        return content

    async def print_judge_ruling(self, ruling: str) -> None:
        """发送裁决内容"""
        await self._send("ruling", {"content": ruling})

    async def print_winner(self, winner: Side | None) -> None:
        """发送胜方结果"""
        winner_value = winner.value if winner else "draw"
        await self._send("winner", {"winner": winner_value})