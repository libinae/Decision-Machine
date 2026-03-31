"""Web 流式生成器 - 流式发送到 WebSocket"""

from typing import Any

from fastapi import WebSocket

from agentscope.agent import ReActAgent
from agentscope.message import Msg


class WebStreamGenerator:
    """Web 版流式生成器，通过 WebSocket 发送文本片段"""

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket

    async def _send_chunk(self, text: str) -> None:
        """发送文本片段"""
        await self.websocket.send_json({"type": "speech_chunk", "data": {"text": text}})

    async def _send_speech_end(self) -> None:
        """发送发言结束标记"""
        await self.websocket.send_json({"type": "speech_end", "data": {}})

    async def generate(
        self,
        agent: ReActAgent,
        model: Any,
        prompt: str,
        sys_prompt_override: str | None = None,
    ) -> str:
        """异步流式生成文本，通过 WebSocket 发送"""

        sys_prompt = sys_prompt_override or agent.sys_prompt

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt},
        ]

        content_parts: list[str] = []
        prev_len = 0

        async for chunk in await model(messages):
            if chunk:
                full_text = chunk.content[0].get("text", "") if chunk.content else ""
                if len(full_text) > prev_len:
                    new_text = full_text[prev_len:]
                    await self._send_chunk(new_text)
                    content_parts.append(new_text)
                    prev_len = len(full_text)

        await self._send_speech_end()
        return "".join(content_parts)

    async def generate_non_stream(self, agent: ReActAgent, prompt: str) -> str:
        """非流式生成"""
        msg = Msg("user", prompt, "user")
        response = await agent(msg)
        return response.get_text_content() or ""