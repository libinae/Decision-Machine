from __future__ import annotations

import json

from ..agents import PERSONAS, AgentFactory
from ..config import AppConfig
from ..constants import DEFAULT_BACKGROUND_QUESTIONS, RULING_KEYWORDS
from ..logger import log_error
from ..types import BackgroundQA, DebateResult, Side
from ..ui import TerminalUI
from .grouping import GroupingEngine
from .phases import DebatePhases, OpeningResult


class DebateEngine:
    def __init__(
        self,
        topic: str,
        pros_position: str | None = None,
        cons_position: str | None = None,
        config: AppConfig | None = None,
        ui: TerminalUI | None = None,
    ):
        self.topic = topic
        self.pros_position = pros_position
        self.cons_position = cons_position
        self.config = config or AppConfig.from_env()

        self.ui = ui or TerminalUI()
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
            # 更新正反方立场（由 AI 分析得出）
            self.pros_position = grouping.pros_position
            self.cons_position = grouping.cons_position
            self.ui.set_positions(self.pros_position, self.cons_position)
            self.all_speeches.extend(stances)
        except Exception as e:
            log_error(f"分组阶段出错：{e}", exc_info=True)
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

        # 提取开篇陈词的 Speech 对象
        if isinstance(opening, OpeningResult):
            opening_list = [
                opening.pros_first,
                opening.cons_first,
                opening.cons_second,
                opening.pros_second,
            ]
        elif opening is None:
            opening_list = []
        else:
            opening_list = list(opening)

        # 提取结辩陈词的 Speech 对象（tuple -> list）
        if isinstance(closing, tuple):
            closing_list = list(closing)
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
            questions = DEFAULT_BACKGROUND_QUESTIONS

        answers: list[str] = []
        for i, q in enumerate(questions, 1):
            answer = self.ui.print_qa_question(i, q)
            answers.append(answer if answer else "（未回答）")

        return BackgroundQA(questions=questions, answers=answers)

    def _determine_winner(self, ruling: str) -> Side | None:
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
