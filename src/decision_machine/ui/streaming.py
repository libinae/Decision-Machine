"""流式生成公共模块

提取 grouping.py 和 phases.py 中重复的流式生成逻辑
"""

from typing import Any

from agentscope.agent import ReActAgent
from agentscope.message import Msg


class StreamGenerator:
    """统一的流式文本生成器"""

    def __init__(self, print_output: bool = True):
        self.print_output = print_output

    async def generate(
        self,
        agent: ReActAgent,
        model: Any,
        prompt: str,
        sys_prompt_override: str | None = None,
    ) -> str:
        """异步流式生成文本

        Args:
            agent: ReActAgent 实例
            model: DashScopeChatModel 实例
            prompt: 用户提示词
            sys_prompt_override: 可选的系统提示词覆盖

        Returns:
            生成的完整文本
        """
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
                    if self.print_output:
                        print(new_text, end="", flush=True)
                    content_parts.append(new_text)
                    prev_len = len(full_text)

        if self.print_output:
            print()

        return "".join(content_parts)

    async def generate_non_stream(
        self,
        agent: ReActAgent,
        prompt: str,
    ) -> str:
        """非流式生成（用于需要完整响应的场景）

        Args:
            agent: ReActAgent 实例
            prompt: 用户提示词

        Returns:
            生成的完整文本
        """
        msg = Msg("user", prompt, "user")
        response = await agent(msg)
        return response.get_text_content() or ""
