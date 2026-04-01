"""网络搜索工具模块

为智能体提供网络搜索能力，在讨论分组阶段搜索相关信息
"""

import asyncio
from typing import Any

from ddgs import DDGS


class WebSearchTool:
    """网络搜索工具"""

    def __init__(self, max_results: int = 5):
        self.max_results = max_results
        self._cache: dict[str, list[dict[str, str]]] = {}

    def search(self, query: str) -> str:
        """执行网络搜索

        Args:
            query: 搜索关键词

        Returns:
            搜索结果摘要文本
        """
        # 检查缓存
        if query in self._cache:
            return self._format_results(self._cache[query])

        try:
            results = []
            with DDGS() as ddgs:
                search_results = list(ddgs.text(query, max_results=self.max_results))

            for r in search_results:
                results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("body", "")[:500],  # 限制长度
                    "url": r.get("href", ""),
                })

            self._cache[query] = results
            return self._format_results(results)

        except Exception as e:
            return f"搜索失败: {str(e)}"

    def _format_results(self, results: list[dict[str, str]]) -> str:
        """格式化搜索结果"""
        if not results:
            return "未找到相关结果"

        lines = ["【搜索结果】"]
        for i, r in enumerate(results, 1):
            lines.append(f"\n{i}. {r['title']}")
            lines.append(f"   {r['snippet']}")
        return "\n".join(lines)

    async def async_search(self, query: str) -> str:
        """异步搜索（在线程池中执行）"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.search, query)


# 全局搜索工具实例
_search_tool: WebSearchTool | None = None


def get_search_tool() -> WebSearchTool:
    """获取全局搜索工具实例"""
    global _search_tool
    if _search_tool is None:
        _search_tool = WebSearchTool()
    return _search_tool


def create_search_tool_function():
    """创建可用于 AgentScope 的搜索工具函数"""

    def web_search(query: str) -> str:
        """
        网络搜索工具，用于查找与决策主题相关的信息。

        Args:
            query: 搜索关键词，应该简洁明确

        Returns:
            搜索结果摘要
        """
        tool = get_search_tool()
        return tool.search(query)

    return web_search


def format_search_results_for_context(
    persona_name: str,
    query: str,
    results: str
) -> str:
    """格式化搜索结果，用于注入到辩论上下文

    Args:
        persona_name: 人格名称
        query: 搜索关键词
        results: 搜索结果

    Returns:
        格式化的上下文文本
    """
    return f"""
【{persona_name}的网络搜索】
搜索关键词：{query}
{results}
"""


__all__ = ["WebSearchTool", "get_search_tool", "create_search_tool_function", "format_search_results_for_context"]