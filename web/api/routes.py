"""WebSocket 路由 - 处理辩论请求"""

import json
from pathlib import Path
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from web.ui.web_ui import WebUI
from web.ui.web_stream import WebStreamGenerator

import sys

# 添加 src 到路径
project_root = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(project_root))

from agentscope.message import Msg

from decision_machine.agents import PERSONAS, AgentFactory
from decision_machine.config import AppConfig
from decision_machine.constants import (
    DEFAULT_BACKGROUND_QUESTIONS,
    GROUPING_KEYWORDS,
    JUDGE_PERSONA_NAME,
    PERSONA_CONSERVATIVE,
    PERSONA_EMPATHETIC,
    PERSONA_RATIONAL,
    PERSONA_RISK_TAKER,
    RULING_KEYWORDS,
)
from decision_machine.engine.grouping import GroupingEngine
from decision_machine.types import (
    BackgroundQA,
    DebateResult,
    GroupingResult,
    Phase,
    Persona,
    Side,
    Speech,
    Team,
)
from decision_machine.export import format_markdown
from decision_machine.tools import WebSearchTool


async def websocket_debate(websocket: WebSocket):
    """WebSocket 辩论入口"""
    await websocket.accept()

    web_ui = WebUI(websocket)
    stream_gen = WebStreamGenerator(websocket)

    try:
        # 接收初始请求
        data = await websocket.receive_json()
        topic = data.get("topic", "")

        if not topic:
            await websocket.send_json({"type": "error", "data": {"message": "辩题不能为空"}})
            return

        config = AppConfig.from_env()
        factory = AgentFactory(config, streaming=True)

        # ===== 阶段一：标题和初始化 =====
        await web_ui.print_header(topic)

        await web_ui.print_phase("🎭 初始化五重人格")
        for persona in PERSONAS:
            await web_ui.print_persona_init(persona, success=True)

        await web_ui.print_phase("🗣️ 讨论与分组")

        # ===== 阶段二：分组 =====
        grouping_engine = WebGroupingEngine(
            topic=topic,
            pros_position=None,
            cons_position=None,
            factory=factory,
            ui=web_ui,
            stream_gen=stream_gen,
        )

        grouping, stances = await grouping_engine.run_grouping()
        web_ui.set_positions(grouping.pros_position, grouping.cons_position)

        await web_ui.print_grouping_result(grouping)

        # ===== 阶段三：背景问答 =====
        await web_ui.print_phase("📝 背景信息收集")

        # 让综合人格根据辩题生成问题
        judge_agent_for_qa, _, _ = factory.create_judge(
            persona=grouping.judge,
            topic=topic,
            pros_position=grouping.pros_position,
            cons_position=grouping.cons_position,
            stream=False,
        )

        qa_prompt = f"""【背景信息收集】
辩题：{topic}
正方立场：{grouping.pros_position}
反方立场：{grouping.cons_position}

作为裁判，你需要向用户收集5个关键背景信息，以便辩手更准确地围绕用户的实际情况展开辩论。
请根据辩题，提出5个最重要的问题。

要求：
1. 问题要紧扣辩题，帮助辩手理解用户的具体情况
2. 涵盖年龄/阶段、收入/经济状况、家庭/责任、经验/能力、心态/顾虑等维度
3. 避免重复，每个问题聚焦一个维度

输出格式（只需输出JSON）：
{{
    "questions": [
        "问题1",
        "问题2",
        "问题3",
        "问题4",
        "问题5"
    ]
}}

只需输出JSON，不要有其他内容。"""

        from agentscope.message import Msg
        qa_msg = Msg("user", qa_prompt, "user")
        qa_response = await judge_agent_for_qa(qa_msg)
        qa_result_text = qa_response.get_text_content() or ""

        questions = []
        try:
            if "{" in qa_result_text and "}" in qa_result_text:
                start = qa_result_text.find("{")
                end = qa_result_text.rfind("}") + 1
                qa_result = json.loads(qa_result_text[start:end])
                questions = qa_result.get("questions", [])
        except Exception:
            pass

        # 如果AI生成失败，使用默认问题
        if not questions or len(questions) < 3:
            questions = DEFAULT_BACKGROUND_QUESTIONS[:5]

        await web_ui.print_qa_intro()
        answers: list[str] = []
        for i, q in enumerate(questions[:5], 1):
            answer = await web_ui.print_qa_question(i, q)
            answers.append(answer)

        background_qa = BackgroundQA(questions=questions[:5], answers=answers)

        # ===== 阶段四：网络检索（可选，出错则跳过） =====
        await web_ui.print_phase("🌐 网络检索资料")
        print("[DEBUG] 开始网络检索阶段...")

        # 搜索结果默认为空，出错时直接跳过
        persona_search_results: dict[str, str] = {}
        search_enabled = True

        try:
            import asyncio
            from concurrent.futures import ThreadPoolExecutor

            # 每个辩手生成搜索关键词
            debater_info = [
                (grouping.pros_team.first_debater, "pros", grouping.pros_position),
                (grouping.pros_team.second_debater, "pros", grouping.pros_position),
                (grouping.cons_team.first_debater, "cons", grouping.cons_position),
                (grouping.cons_team.second_debater, "cons", grouping.cons_position),
            ]

            search_keywords: dict[str, str] = {}
            executor = ThreadPoolExecutor(max_workers=4)

            for persona, side, position in debater_info:
                try:
                    temp_agent, _, temp_model = factory.create_debater(
                        persona=persona,
                        topic=topic,
                        pros_position=grouping.pros_position,
                        cons_position=grouping.cons_position,
                        side=side,
                        background_qa=background_qa,
                        stream=False,
                    )

                    keyword_prompt = f"生成一个搜索关键词用于搜索支持【{position}】的资料。只输出关键词："
                    keyword_msg = Msg("user", keyword_prompt, "user")

                    keyword_response = await asyncio.wait_for(
                        temp_agent(keyword_msg),
                        timeout=15.0
                    )
                    keyword = keyword_response.get_text_content() or topic
                    keyword = keyword.strip().split("\n")[0].strip()[:50]

                except Exception as e:
                    keyword = topic
                    print(f"[DEBUG] {persona.name} 关键词生成失败: {e}")

                search_keywords[persona.name] = keyword
                print(f"[DEBUG] {persona.name} 关键词: {keyword}")

                await websocket.send_json({
                    "type": "search_keyword",
                    "data": {
                        "speaker": f"{persona.icon} {persona.name}",
                        "position": "正方" if side == "pros" else "反方",
                        "keyword": keyword,
                    }
                })

            # 执行搜索
            print("[DEBUG] 执行并行搜索...")
            search_tool = WebSearchTool(max_results=3, timeout=10)

            def sync_search(keyword: str) -> str:
                return search_tool.search(keyword)

            loop = asyncio.get_running_loop()
            search_tasks = [
                loop.run_in_executor(executor, sync_search, kw)
                for kw in search_keywords.values()
            ]

            search_results = await asyncio.wait_for(
                asyncio.gather(*search_tasks, return_exceptions=True),
                timeout=60.0
            )

            # 构建结果映射
            persona_names = list(search_keywords.keys())
            for i, name in enumerate(persona_names):
                result = search_results[i]
                if isinstance(result, Exception):
                    persona_search_results[name] = ""
                else:
                    persona_search_results[name] = result or ""

            print(f"[DEBUG] 搜索完成")

        except asyncio.TimeoutError:
            print("[DEBUG] 搜索阶段超时，跳过")
            search_enabled = False
        except Exception as e:
            print(f"[DEBUG] 搜索阶段出错: {e}")
            search_enabled = False
        finally:
            if 'executor' in locals():
                executor.shutdown(wait=False)

        def get_search_context_for_debater(persona: Persona) -> str:
            """获取辩手相关的搜索结果"""
            if not search_enabled:
                return ""
            own_result = persona_search_results.get(persona.name, "")
            teammate = None
            if persona == grouping.pros_team.first_debater:
                teammate = grouping.pros_team.second_debater
            elif persona == grouping.pros_team.second_debater:
                teammate = grouping.pros_team.first_debater
            elif persona == grouping.cons_team.first_debater:
                teammate = grouping.cons_team.second_debater
            elif persona == grouping.cons_team.second_debater:
                teammate = grouping.cons_team.first_debater

            teammate_result = persona_search_results.get(teammate.name, "") if teammate else ""
            if own_result or teammate_result:
                return f"{own_result}\n\n【队友补充资料】\n{teammate_result}"
            return ""

        # ===== 阶段五：创建辩手 =====
        await web_ui.print_phase("🎤 开篇陈词")

        # 创建辩手 agent（带个性化搜索结果作为辩论依据）
        pros_first_agent, _, pros_first_model = factory.create_debater(
            persona=grouping.pros_team.first_debater,
            topic=topic,
            pros_position=grouping.pros_position,
            cons_position=grouping.cons_position,
            side="pros",
            background_qa=background_qa,
            search_context=get_search_context_for_debater(grouping.pros_team.first_debater),
        )
        pros_second_agent, _, pros_second_model = factory.create_debater(
            persona=grouping.pros_team.second_debater,
            topic=topic,
            pros_position=grouping.pros_position,
            cons_position=grouping.cons_position,
            side="pros",
            background_qa=background_qa,
            search_context=get_search_context_for_debater(grouping.pros_team.second_debater),
        )
        cons_first_agent, _, cons_first_model = factory.create_debater(
            persona=grouping.cons_team.first_debater,
            topic=topic,
            pros_position=grouping.pros_position,
            cons_position=grouping.cons_position,
            side="cons",
            background_qa=background_qa,
            search_context=get_search_context_for_debater(grouping.cons_team.first_debater),
        )
        cons_second_agent, _, cons_second_model = factory.create_debater(
            persona=grouping.cons_team.second_debater,
            topic=topic,
            pros_position=grouping.pros_position,
            cons_position=grouping.cons_position,
            side="cons",
            background_qa=background_qa,
            search_context=get_search_context_for_debater(grouping.cons_team.second_debater),
        )

        judge_agent, _, judge_model = factory.create_judge(
            persona=grouping.judge,
            topic=topic,
            pros_position=grouping.pros_position,
            cons_position=grouping.cons_position,
        )

        # ===== 阶段五：开篇陈词 =====
        all_speeches: list[Speech] = list(stances)

        opening_order = [
            (pros_first_agent, pros_first_model, Side.PROS, grouping.pros_team.first_debater, "正方一辩"),
            (cons_first_agent, cons_first_model, Side.CONS, grouping.cons_team.first_debater, "反方一辩"),
            (cons_second_agent, cons_second_model, Side.CONS, grouping.cons_team.second_debater, "反方二辩"),
            (pros_second_agent, pros_second_model, Side.PROS, grouping.pros_team.second_debater, "正方二辩"),
        ]

        opening_speeches: list[Speech] = []
        for agent, model, side, persona, position in opening_order:
            my_position = grouping.pros_position if side == Side.PROS else grouping.cons_position
            opponent_position = grouping.cons_position if side == Side.PROS else grouping.pros_position

            prompt = f"""【开篇陈词】

你是 {position}（{persona.icon} {persona.name}）。
你支持的立场：【{my_position}】
你需要反驳：【{opponent_position}】

请发表你的开篇陈词：
1. 明确表明你的立场
2. 提出你方的核心论点（2-3个）
3. 用你的【人格特点】来论证
4. 字数控制在200-300字

请直接开始你的发言："""

            # 发送发言开始标记
            await websocket.send_json({
                "type": "speech_start",
                "data": {
                    "speaker": f"{persona.icon} {persona.name}",
                    "position": position,
                    "side": side.value,
                }
            })

            content = await stream_gen.generate(agent, model, prompt, sys_prompt_override=agent.sys_prompt)

            speech = Speech(
                speaker=f"{persona.icon} {persona.name}",
                content=content,
                side=side,
                persona=persona,
                round=0,
                phase=Phase.OPENING,
                position=position,
            )
            opening_speeches.append(speech)
            all_speeches.append(speech)

        # ===== 阶段六：自由辩论 =====
        await web_ui.print_phase("💬 自由辩论")

        debate_agents = [
            (pros_first_agent, pros_first_model, Side.PROS, grouping.pros_team.first_debater, "正方一辩"),
            (cons_first_agent, cons_first_model, Side.CONS, grouping.cons_team.first_debater, "反方一辩"),
            (cons_second_agent, cons_second_model, Side.CONS, grouping.cons_team.second_debater, "反方二辩"),
            (pros_second_agent, pros_second_model, Side.PROS, grouping.pros_team.second_debater, "正方二辩"),
        ]

        current_idx = 0
        max_rounds = config.debate.max_debate_rounds

        for round_num in range(1, max_rounds + 1):
            agent, model, side, persona, position = debate_agents[current_idx]

            # 构建精简上下文
            recent_speeches = all_speeches[-6:] if len(all_speeches) > 6 else all_speeches
            context_lines = []
            for s in recent_speeches:
                side_name = "正" if s.side == Side.PROS else "反"
                context_lines.append(f"[{side_name}]{s.speaker}：{s.content[:100]}...")
            context = "\n".join(context_lines)

            my_position = grouping.pros_position if side == Side.PROS else grouping.cons_position
            opponent_side = "反方" if side == Side.PROS else "正方"

            prompt = f"""【第{round_num}轮自由辩论】

你是 {position}（{persona.icon} {persona.name}）。
你支持：【{my_position}】

【最近的辩论】
{context}

【你的任务】
针对{opponent_side}最近的论点进行反驳，同时强化你的立场。
保持你【{persona.name}】的特点和风格。
言简意赅，150字左右。

请直接发言："""

            await websocket.send_json({
                "type": "speech_start",
                "data": {
                    "speaker": f"{persona.icon} {persona.name}",
                    "position": f"第{round_num}轮 {position}",
                    "side": side.value,
                    "round": round_num,
                }
            })

            content = await stream_gen.generate(agent, model, prompt, sys_prompt_override=agent.sys_prompt)

            speech = Speech(
                speaker=f"{persona.icon} {persona.name}",
                content=content,
                side=side,
                persona=persona,
                round=round_num,
                phase=Phase.FREE_DEBATE,
                position=position,
            )
            all_speeches.append(speech)
            current_idx = (current_idx + 1) % len(debate_agents)

        # ===== 阶段七：结辩 =====
        await web_ui.print_phase("🏁 结辩陈词")

        # 构建辩论总结
        recent_speeches = all_speeches[-8:] if len(all_speeches) > 8 else all_speeches
        context_lines = []
        for s in recent_speeches:
            side_name = "正" if s.side == Side.PROS else "反"
            context_lines.append(f"[{side_name}]{s.speaker}：{s.content[:80]}...")
        context = "\n".join(context_lines)

        # 正方结辩
        pros_prompt = f"""【正方结辩】

你是 正方一辩（{grouping.pros_team.first_debater.icon} {grouping.pros_team.first_debater.name}）。
你支持：【{grouping.pros_position}】

【辩论回顾】
{context}

【你的任务】
作为正方最后陈述，请：
1. 总结正方的核心论点
2. 指出反方论点的漏洞
3. 再次强调你的立场价值
4. 保持你的人格特点

150字左右，直接发言："""

        await websocket.send_json({
            "type": "speech_start",
            "data": {
                "speaker": f"{grouping.pros_team.first_debater.icon} {grouping.pros_team.first_debater.name}",
                "position": "正方结辩",
                "side": "pros",
            }
        })

        pros_content = await stream_gen.generate(
            pros_first_agent, pros_first_model, pros_prompt, sys_prompt_override=pros_first_agent.sys_prompt
        )
        pros_speech = Speech(
            speaker=f"{grouping.pros_team.first_debater.icon} {grouping.pros_team.first_debater.name}",
            content=pros_content,
            side=Side.PROS,
            persona=grouping.pros_team.first_debater,
            round=0,
            phase=Phase.CLOSING,
            position="正方一辩",
        )
        all_speeches.append(pros_speech)

        # 反方结辩
        cons_prompt = f"""【反方结辩】

你是 反方一辩（{grouping.cons_team.first_debater.icon} {grouping.cons_team.first_debater.name}）。
你支持：【{grouping.cons_position}】

【辩论回顾】
{context}

【你的任务】
作为反方最后陈述，请：
1. 总结反方的核心论点
2. 指出正方论点的漏洞
3. 再次强调你的立场价值
4. 保持你的人格特点

150字左右，直接发言："""

        await websocket.send_json({
            "type": "speech_start",
            "data": {
                "speaker": f"{grouping.cons_team.first_debater.icon} {grouping.cons_team.first_debater.name}",
                "position": "反方结辩",
                "side": "cons",
            }
        })

        cons_content = await stream_gen.generate(
            cons_first_agent, cons_first_model, cons_prompt, sys_prompt_override=cons_first_agent.sys_prompt
        )
        cons_speech = Speech(
            speaker=f"{grouping.cons_team.first_debater.icon} {grouping.cons_team.first_debater.name}",
            content=cons_content,
            side=Side.CONS,
            persona=grouping.cons_team.first_debater,
            round=0,
            phase=Phase.CLOSING,
            position="反方一辩",
        )
        all_speeches.append(cons_speech)

        # ===== 阶段八：裁判裁决 =====
        await web_ui.print_phase("⚖️ 裁判裁决")

        # 构建完整辩论记录
        all_speech_lines = []
        for s in all_speeches:
            side_name = "正方" if s.side == Side.PROS else "反方"
            all_speech_lines.append(f"[{side_name}-{s.position}]{s.speaker}：{s.content}")
        debate_record = "\n".join(all_speech_lines)

        ruling_prompt = f"""【裁判裁决】

你是裁判（{grouping.judge.icon} {grouping.judge.name}）。

辩题：{topic}
正方立场：{grouping.pros_position}
反方立场：{grouping.cons_position}

【完整辩论记录】
{debate_record}

【你的任务】
作为裁判，请给出公正的裁决：

1. **正方核心论点总结**（2-3条）
2. **反方核心论点总结**（2-3条）
3. **双方论证评价**（逻辑性、说服力、人格特点发挥）
4. **最终裁决**：正方胜 / 反方胜 / 平局
5. **裁决理由**（100字左右）
6. **给决策者的建议**（结合用户背景，给出具体可行的建议）

请客观公正地裁决："""

        await websocket.send_json({
            "type": "speech_start",
            "data": {
                "speaker": f"{grouping.judge.icon} {grouping.judge.name}",
                "position": "裁判",
                "side": "judge",
            }
        })

        ruling = await stream_gen.generate(judge_agent, judge_model, ruling_prompt)

        # 判定胜方
        winner = _determine_winner(ruling)

        await web_ui.print_winner(winner)

        # ===== 返回结果 =====
        result = DebateResult(
            topic=topic,
            grouping=grouping,
            speeches=all_speeches,
            judge_ruling=ruling,
            winner=winner,
            grouping_reason=grouping.reason,
            background_qa=background_qa,
        )

        await websocket.send_json({
            "type": "complete",
            "data": {"winner": winner.value if winner else "draw"}
        })

        # 等待下载请求
        try:
            download_req = await websocket.receive_json()
            if download_req.get("type") == "download":
                report = format_markdown(result)
                await websocket.send_json({"type": "report", "data": {"content": report}})
        except Exception:
            pass

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"type": "error", "data": {"message": str(e)}})


def _determine_winner(ruling: str) -> Side | None:
    """判定胜方"""
    if not ruling:
        return None

    draw_keywords = RULING_KEYWORDS["draw"]
    if any(kw in ruling for kw in draw_keywords):
        return None

    if RULING_KEYWORDS["pros_win"] in ruling:
        return Side.PROS
    if RULING_KEYWORDS["cons_win"] in ruling:
        return Side.CONS

    return None


class WebGroupingEngine(GroupingEngine):
    """Web 版分组引擎"""

    def __init__(
        self,
        topic: str,
        pros_position: str | None,
        cons_position: str | None,
        factory: AgentFactory,
        ui: WebUI,
        stream_gen: WebStreamGenerator,
    ):
        super().__init__(
            topic=topic,
            pros_position=pros_position,
            cons_position=cons_position,
            factory=factory,
            ui=ui,
            stream_gen=stream_gen,
        )
        self.stream_gen = stream_gen

    async def _analyze_positions(self) -> None:
        """让综合人格分析辩题，确定正反方立场（输出分析结果）"""
        synthesizer = next(p for p in PERSONAS if p.name == JUDGE_PERSONA_NAME)

        await self.websocket_send("speech_start", {
            "speaker": f"{synthesizer.icon} {synthesizer.name}",
            "position": "分析辩题",
            "side": "judge",
        })

        prompt = f"""分析以下决策问题，提取正反方立场：

决策问题：{self.topic}

规则：
- 正方 = 激进/改变/行动/冒险的选项
- 反方 = 保守/维持现状/稳健的选项

请先简要说明你的分析过程（50字左右），然后输出正反方立场。
格式如下：
【分析】你的分析...
【正方】选项
【反方】选项"""

        judge_agent, _, judge_model = self.factory.create_judge(
            persona=synthesizer,
            topic=self.topic,
            pros_position="待确定",
            cons_position="待确定",
            stream=True,
        )

        result_text = await self.stream_gen.generate(judge_agent, judge_model, prompt)

        # 解析正反方立场
        try:
            if "【正方】" in result_text and "【反方】" in result_text:
                pros_start = result_text.find("【正方】") + 4
                pros_end = result_text.find("【反方】", pros_start)
                self.pros_position = result_text[pros_start:pros_end].strip()

                cons_start = result_text.find("【反方】") + 4
                cons_end = result_text.find("\n", cons_start)
                if cons_end == -1:
                    cons_end = len(result_text)
                self.cons_position = result_text[cons_start:cons_end].strip()
        except Exception:
            pass

        if not self.pros_position or not self.cons_position:
            try:
                if "{" in result_text and "}" in result_text:
                    start = result_text.find("{")
                    end = result_text.rfind("}") + 1
                    result = json.loads(result_text[start:end])
                    self.pros_position = result.get("正方", "")
                    self.cons_position = result.get("反方", "")
            except Exception:
                pass

        if not self.pros_position or not self.cons_position:
            self._fallback_parse_topic()

    async def _collect_stances(self) -> list[Speech]:
        """四位辩手表态（通过 WebSocket 发送）"""
        stances: list[Speech] = []

        debater_personas = [p for p in PERSONAS if p.name != JUDGE_PERSONA_NAME]

        for persona in debater_personas:
            agent, _, model = self.factory.create_debater(
                persona=persona,
                topic=self.topic,
                pros_position=self.pros_position,
                cons_position=self.cons_position,
                side="neutral",
                stream=True,
            )

            # 发送发言开始消息
            await self.websocket_send("speech_start", {
                "speaker": f"{persona.icon} {persona.name}",
                "position": "表态",
                "side": "neutral",
            })

            prompt = f"""【表态环节】
辩题：{self.topic}
正方立场：{self.pros_position}
反方立场：{self.cons_position}

作为 {persona.icon} {persona.name}，请表达你对这个问题的看法：
1. 你的第一反应是什么？
2. 你倾向于支持正方还是反方？
3. 简要说明你的理由。

保持人格特点，150-200字即可。"""

            content = await self.stream_gen.generate(agent, model, prompt)
            side = self._infer_side(content)
            stance = Speech(
                speaker=f"{persona.icon} {persona.name}",
                content=content,
                side=side,
                persona=persona,
                round=0,
                phase=Phase.GROUPING,
            )
            stances.append(stance)

        return stances

    async def run_grouping(self) -> tuple[GroupingResult, list[Speech]]:
        """运行分组流程"""
        if not self.pros_position or not self.cons_position:
            await self._analyze_positions()

        stances = await self._collect_stances()
        grouping = await self._determine_grouping(stances)
        return grouping, stances

    async def _determine_grouping(self, stances: list[Speech]) -> GroupingResult:
        """综合人格进行分组并输出理由"""
        synthesizer = next(p for p in PERSONAS if p.name == JUDGE_PERSONA_NAME)
        debater_personas = [p for p in PERSONAS if p.name != JUDGE_PERSONA_NAME]

        stance_summary = "\n".join([
            f"- {s.persona.icon} {s.persona.name}：{'支持正方' if s.side == Side.PROS else '支持反方' if s.side == Side.CONS else '中立'}"
            for s in stances
        ])
        debater_profiles = "\n".join([f"- {p.icon}{p.name}：{p.description}" for p in debater_personas])

        # 发送发言开始消息
        await self.websocket_send("speech_start", {
            "speaker": f"{synthesizer.icon} {synthesizer.name}",
            "position": "分组决策",
            "side": "judge",
        })

        prompt = f"""【分组决策】
辩题：{self.topic}
正方立场：{self.pros_position}
反方立场：{self.cons_position}

辩手特点：
{debater_profiles}

初始表态：
{stance_summary}

你是裁判，请分配正反方（各2人），并说明分组理由。

格式要求：
【分组】
正方一辩：人格名称
正方二辩：人格名称
反方一辩：人格名称
反方二辩：人格名称

【理由】
简要说明为什么这样分组（100字左右），考虑：
- 辩手的初始倾向
- 人格特点与立场匹配
- 辩论策略平衡"""

        judge_agent, _, judge_model = self.factory.create_judge(
            persona=synthesizer,
            topic=self.topic,
            pros_position=self.pros_position,
            cons_position=self.cons_position,
            stream=True,
        )

        result_text = await self.stream_gen.generate(judge_agent, judge_model, prompt)

        # 解析分组结果
        result = {}
        reason = ""
        try:
            if "【分组】" in result_text:
                grouping_start = result_text.find("【分组】") + 4
                grouping_end = result_text.find("【理由】", grouping_start)
                if grouping_end == -1:
                    grouping_end = len(result_text)
                grouping_text = result_text[grouping_start:grouping_end]

                for line in grouping_text.split("\n"):
                    line = line.strip()
                    if "正方一辩" in line:
                        result["正方一辩"] = line.split("：")[-1].strip() if "：" in line else line.split(":")[-1].strip()
                    elif "正方二辩" in line:
                        result["正方二辩"] = line.split("：")[-1].strip() if "：" in line else line.split(":")[-1].strip()
                    elif "反方一辩" in line:
                        result["反方一辩"] = line.split("：")[-1].strip() if "：" in line else line.split(":")[-1].strip()
                    elif "反方二辩" in line:
                        result["反方二辩"] = line.split("：")[-1].strip() if "：" in line else line.split(":")[-1].strip()

            if "【理由】" in result_text:
                reason_start = result_text.find("【理由】") + 4
                reason = result_text[reason_start:].strip()
        except Exception:
            pass

        if not result:
            try:
                if "{" in result_text and "}" in result_text:
                    start = result_text.find("{")
                    end = result_text.rfind("}") + 1
                    result = json.loads(result_text[start:end])
            except Exception:
                result = {}

        def find_persona(name: str) -> Persona:
            for p in debater_personas:
                if p.name in name:
                    return p
            return debater_personas[0]

        pros_first_name = result.get("正方一辩", PERSONA_RISK_TAKER)
        pros_second_name = result.get("正方二辩", PERSONA_EMPATHETIC)
        cons_first_name = result.get("反方一辩", PERSONA_RATIONAL)
        cons_second_name = result.get("反方二辩", PERSONA_CONSERVATIVE)

        pros_team = Team(
            side=Side.PROS,
            first_debater=find_persona(pros_first_name),
            second_debater=find_persona(pros_second_name),
        )
        cons_team = Team(
            side=Side.CONS,
            first_debater=find_persona(cons_first_name),
            second_debater=find_persona(cons_second_name),
        )

        return GroupingResult(
            pros_team=pros_team,
            cons_team=cons_team,
            judge=synthesizer,
            pros_position=self.pros_position,
            cons_position=self.cons_position,
            reason=reason,
        )

    async def websocket_send(self, msg_type: str, data: Any) -> None:
        """发送 WebSocket 消息"""
        await self.ui.websocket.send_json({"type": msg_type, "data": data})

    async def _stream_generate_print(self, agent, model, prompt: str) -> str:
        """流式生成并发送到 WebSocket"""
        return await self.stream_gen.generate(agent, model, prompt)