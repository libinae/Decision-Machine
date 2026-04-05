"""网络搜索工具模块

为智能体提供网络搜索能力，在讨论分组阶段搜索相关信息
"""

import asyncio
import time
from typing import Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from ddgs import DDGS


class WebSearchTool:
    """网络搜索工具"""

    def __init__(self, max_results: int = 5, timeout: int = 10):
        self.max_results = max_results
        self.timeout = timeout
        self._cache: dict[str, list[dict[str, str]]] = {}
        self._executor = ThreadPoolExecutor(max_workers=2)

    def _do_search(self, query: str) -> list[dict[str, str]]:
        """执行搜索（同步方法）"""
        try:
            with DDGS(timeout=self.timeout) as ddgs:
                search_results = list(ddgs.text(query, max_results=self.max_results))

            results = []
            for r in search_results:
                results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("body", "")[:500],
                    "url": r.get("href", ""),
                })
            return results
        except Exception as e:
            print(f"[WebSearch] 搜索出错: {e}")
            return []

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
            # 使用线程池执行，带超时
            future = self._executor.submit(self._do_search, query)
            results = future.result(timeout=self.timeout + 5)

            self._cache[query] = results
            return self._format_results(results)

        except FuturesTimeoutError:
            print(f"[WebSearch] 搜索超时: {query}")
            return "搜索超时"
        except Exception as e:
            print(f"[WebSearch] 搜索异常: {e}")
            return "搜索失败"

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
        """异步搜索"""
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(self._executor, self.search, query)
        except Exception as e:
            return f"搜索失败: {str(e)}"


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