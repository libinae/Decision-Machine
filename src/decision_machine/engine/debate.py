from __future__ import annotations

import json
from typing import Optional

from ..types import Side, DebateResult, BackgroundQA
from ..config import AppConfig
from ..agents import AgentFactory, PERSONAS
from ..ui import TerminalUI
from .phases import DebatePhases
from .grouping import GroupingEngine


class DebateEngine:

    def __init__(
        self,
        topic: str,
        pros_position: str,
        cons_position: str,
        config: AppConfig | None = None,
    ):
        self.topic = topic
        self.pros_position = pros_position
        self.cons_position = cons_position
        self.config = config or AppConfig.from_env()

        self.ui = TerminalUI()
        self.ui.set_positions(pros_position, cons_position)
        self.factory = AgentFactory(self.config, streaming=False)
        self.all_speeches = []
        self.background_qa: BackgroundQA | None = None

    async def run(self) -> DebateResult:
        self.ui.print_header(self.topic)

        self.ui.print_phase("初始化5位人格")
        for persona in PERSONAS:
            self.ui.print_persona_init(persona, success=True)

        grouping_engine = GroupingEngine(
            topic=self.topic,
            pros_position=self.pros_position,
            cons_position=self.cons_position,
            factory=self.factory,
            ui=self.ui,
        )

        self.ui.print_phase("阶段一：讨论与分组")

        try:
            grouping, stances = await grouping_engine.run_grouping()
            self.all_speeches.extend(stances)
        except Exception as e:
            print(f"分组阶段出错：{e}")
            raise

        self.ui.print_grouping_result(grouping)

        judge_agent, _, _ = self.factory.create_judge(
            persona=grouping.judge,
            topic=self.topic,
            pros_position=self.pros_position,
            cons_position=self.cons_position,
            stream=False,
        )
        self.background_qa = await self._run_background_qa(judge_agent)

        self.factory.streaming = True
        _, _, judge_model = self.factory.create_judge(
            persona=grouping.judge,
            topic=self.topic,
            pros_position=self.pros_position,
            cons_position=self.cons_position,
            stream=True,
        )
        pros_first_agent, _, pros_first_model = self.factory.create_debater(
            persona=grouping.pros_team.first_debater,
            topic=self.topic,
            pros_position=self.pros_position,
            cons_position=self.cons_position,
            side="pros",
            background_qa=self.background_qa,
        )
        pros_second_agent, _, pros_second_model = self.factory.create_debater(
            persona=grouping.pros_team.second_debater,
            topic=self.topic,
            pros_position=self.pros_position,
            cons_position=self.cons_position,
            side="pros",
            background_qa=self.background_qa,
        )
        cons_first_agent, _, cons_first_model = self.factory.create_debater(
            persona=grouping.cons_team.first_debater,
            topic=self.topic,
            pros_position=self.pros_position,
            cons_position=self.cons_position,
            side="cons",
            background_qa=self.background_qa,
        )
        cons_second_agent, _, cons_second_model = self.factory.create_debater(
            persona=grouping.cons_team.second_debater,
            topic=self.topic,
            pros_position=self.pros_position,
            cons_position=self.cons_position,
            side="cons",
            background_qa=self.background_qa,
        )

        phases = DebatePhases(
            ui=self.ui,
            grouping=grouping,
            topic=self.topic,
            pros_position=self.pros_position,
            cons_position=self.cons_position,
            pros_first_agent=pros_first_agent,
            pros_second_agent=pros_second_agent,
            cons_first_agent=cons_first_agent,
            cons_second_agent=cons_second_agent,
            judge_agent=judge_agent,
            pros_first_model=pros_first_model,
            pros_second_model=pros_second_model,
            cons_first_model=cons_first_model,
            cons_second_model=cons_second_model,
            judge_model=judge_model,
            max_rounds=self.config.debate.max_debate_rounds,
            streaming=True,
            background_qa=self.background_qa,
        )

        opening = await phases.run_opening_statements()

        free_debate = await phases.run_free_debate()
        self.all_speeches.extend(free_debate)

        closing = await phases.run_closing_statements()

        ruling = await phases.run_judge_ruling()

        winner = self._determine_winner(ruling)

        self.ui.print_winner(winner)

        if isinstance(opening, list):
            opening_list = opening
        elif opening is None:
            opening_list = []
        else:
            opening_list = [opening]

        if isinstance(closing, list):
            closing_list = closing
        elif closing is None:
            closing_list = []
        else:
            closing_list = [closing]

        return DebateResult(
            topic=self.topic,
            grouping=grouping,
            speeches=self.all_speeches + opening_list + closing_list,
            judge_ruling=ruling,
            winner=winner,
            grouping_reason=grouping.reason,
            background_qa=self.background_qa,
        )

    async def _run_background_qa(self, judge_agent) -> BackgroundQA:
        self.ui.print_phase("阶段二：背景信息收集")
        self.ui.print_qa_intro()

        prompt = f"""【背景信息收集】
辩题：{self.topic}
正方立场：{self.pros_position}
反方立场：{self.cons_position}

作为裁判，你需要向用户收集5个关键背景信息，以便辩手更准确地围绕用户的实际情况展开辩论。
请根据辩题，提出5个最重要的问题（无需解释，直接列出问题即可）。

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
        msg = Msg("user", prompt, "user")
        response = await judge_agent(msg)
        result_text = response.get_text_content() or ""

        questions = []
        try:
            if "{" in result_text and "}" in result_text:
                start = result_text.find("{")
                end = result_text.rfind("}") + 1
                result = json.loads(result_text[start:end])
                questions = result.get("questions", [])
        except Exception:
            pass

        if not questions:
            questions = [
                f"你目前的年龄和所处的人生阶段是什么？",
                f"你的经济状况如何？有没有足够的储蓄或收入来源？",
                f"你的家庭情况是怎样的？有没有需要照顾的人？",
                f"你目前的工作经验和能力积累到什么程度？",
                f"你内心最大的顾虑或障碍是什么？",
            ]

        answers: list[str] = []
        for i, q in enumerate(questions, 1):
            answer = self.ui.print_qa_question(i, q)
            answers.append(answer if answer else "（未回答）")

        return BackgroundQA(questions=questions, answers=answers)

    def _determine_winner(self, ruling: str) -> Optional[Side]:
        if not ruling:
            return None

        if "平局" in ruling or "和局" in ruling:
            return None

        if "正方胜" in ruling:
            return Side.PROS
        if "反方胜" in ruling:
            return Side.CONS

        return None
