from typing import Optional, List
from dataclasses import dataclass

from agentscope.agent import ReActAgent
from agentscope.message import Msg

from ..types import Side, Speech, GroupingResult, Phase, BackgroundQA
from ..ui import TerminalUI


@dataclass
class OpeningResult:
    pros_first: Speech
    cons_first: Speech
    cons_second: Speech
    pros_second: Speech


class DebatePhases:

    def __init__(
        self,
        ui: TerminalUI,
        grouping: GroupingResult,
        topic: str,
        pros_position: str,
        cons_position: str,
        pros_first_agent: ReActAgent,
        pros_second_agent: ReActAgent,
        cons_first_agent: ReActAgent,
        cons_second_agent: ReActAgent,
        judge_agent: ReActAgent,
        pros_first_model,
        pros_second_model,
        cons_first_model,
        cons_second_model,
        judge_model,
        max_rounds: int = 10,
        streaming: bool = True,
        background_qa: BackgroundQA | None = None,
    ):
        self.ui = ui
        self.grouping = grouping
        self.topic = topic
        self.pros_position = pros_position
        self.cons_position = cons_position
        self.pros_first_agent = pros_first_agent
        self.pros_second_agent = pros_second_agent
        self.cons_first_agent = cons_first_agent
        self.cons_second_agent = cons_second_agent
        self.judge_agent = judge_agent
        self.pros_first_model = pros_first_model
        self.pros_second_model = pros_second_model
        self.cons_first_model = cons_first_model
        self.cons_second_model = cons_second_model
        self.judge_model = judge_model
        self.max_rounds = max_rounds
        self.streaming = streaming
        self.background_qa = background_qa
        self.speeches: List[Speech] = []

    async def run_opening_statements(self) -> OpeningResult:
        self.ui.print_phase("正式辩论 - 开篇陈词")

        order = [
            (self.pros_first_agent, self.pros_first_model, Side.PROS, self.grouping.pros_team.first_debater, "正方一辩", 1),
            (self.cons_first_agent, self.cons_first_model, Side.CONS, self.grouping.cons_team.first_debater, "反方一辩", 2),
            (self.cons_second_agent, self.cons_second_model, Side.CONS, self.grouping.cons_team.second_debater, "反方二辩", 3),
            (self.pros_second_agent, self.pros_second_model, Side.PROS, self.grouping.pros_team.second_debater, "正方二辩", 4),
        ]

        results: List[Speech] = []
        for agent, model, side, persona, position, step in order:
            self._print_speaker_label(persona.icon, position, side, step=step)
            content = await self._generate_speech(
                agent, model,
                f"【第{step}步开篇陈词】\n你是 {position}，{persona.icon} {persona.name}，请发表开篇陈词。",
                role_context=position,
            )
            speech = Speech(
                speaker=f"{persona.icon} {persona.name}",
                content=content,
                side=side,
                persona=persona,
                round=0,
                phase=Phase.OPENING,
                position=position,
            )
            self.speeches.append(speech)
            results.append(speech)

        return OpeningResult(
            pros_first=results[0],
            cons_first=results[1],
            cons_second=results[2],
            pros_second=results[3],
        )

    async def run_free_debate(self) -> List[Speech]:
        self.ui.print_phase("正式辩论 - 自由辩论")

        debate_agents = [
            (self.pros_first_agent, self.pros_first_model, Side.PROS, self.grouping.pros_team.first_debater, "正方一辩"),
            (self.cons_first_agent, self.cons_first_model, Side.CONS, self.grouping.cons_team.first_debater, "反方一辩"),
            (self.cons_second_agent, self.cons_second_model, Side.CONS, self.grouping.cons_team.second_debater, "反方二辩"),
            (self.pros_second_agent, self.pros_second_model, Side.PROS, self.grouping.pros_team.second_debater, "正方二辩"),
        ]
        current_idx = 0
        for round_num in range(1, self.max_rounds + 1):
            agent, model, side, persona, position = debate_agents[current_idx]
            context = self._build_debate_context()
            prompt = f"""【第{round_num}轮自由辩论】
{context}

你是 {position}，{persona.icon} {persona.name}，请针对对方的观点进行反驳或补充你的论点。
保持人格特点，言简意赅，100-200字即可。"""
            self._print_speaker_label(persona.icon, position, side, step=round_num)
            content = await self._generate_speech(agent, model, prompt, role_context=position)
            speech = Speech(
                speaker=f"{persona.icon} {persona.name}",
                content=content,
                side=side,
                persona=persona,
                round=round_num,
                phase=Phase.FREE_DEBATE,
                position=position,
            )
            self.speeches.append(speech)
            current_idx = (current_idx + 1) % len(debate_agents)
            if round_num >= 10:
                break
        return self.speeches

    async def run_closing_statements(self) -> tuple[Speech, Speech]:
        self.ui.print_phase("正式辩论 - 结辩陈词")

        pros_context = self._build_debate_context()
        pros_prompt = f"""【正方结辩】
{pros_context}

你是 正方一辩，{self.grouping.pros_team.first_debater.icon} {self.grouping.pros_team.first_debater.name}，请做最后的总结陈述，再次强调正方的核心论点和价值。言简意赅，150字左右。"""
        self._print_speaker_label(
            self.grouping.pros_team.first_debater.icon,
            "正方一辩", Side.PROS, phase=Phase.CLOSING,
        )
        pros_content = await self._generate_speech(
            self.pros_first_agent, self.pros_first_model, pros_prompt,
            role_context="正方一辩",
        )
        pros_speech = Speech(
            speaker=f"{self.grouping.pros_team.first_debater.icon} {self.grouping.pros_team.first_debater.name}",
            content=pros_content,
            side=Side.PROS,
            persona=self.grouping.pros_team.first_debater,
            round=0,
            phase=Phase.CLOSING,
            position="正方一辩",
        )
        self.speeches.append(pros_speech)

        cons_prompt = f"""【反方结辩】
{self._build_debate_context()}

你是 反方一辩，{self.grouping.cons_team.first_debater.icon} {self.grouping.cons_team.first_debater.name}，请做最后的总结陈述，再次强调反方的核心论点和价值。言简意赅，150字左右。"""
        self._print_speaker_label(
            self.grouping.cons_team.first_debater.icon,
            "反方一辩", Side.CONS, phase=Phase.CLOSING,
        )
        cons_content = await self._generate_speech(
            self.cons_first_agent, self.cons_first_model, cons_prompt,
            role_context="反方一辩",
        )
        cons_speech = Speech(
            speaker=f"{self.grouping.cons_team.first_debater.icon} {self.grouping.cons_team.first_debater.name}",
            content=cons_content,
            side=Side.CONS,
            persona=self.grouping.cons_team.first_debater,
            round=0,
            phase=Phase.CLOSING,
            position="反方一辩",
        )
        self.speeches.append(cons_speech)
        return pros_speech, cons_speech

    async def run_judge_ruling(self) -> str:
        self.ui.print_phase("裁判裁决")
        judge_icon = self.grouping.judge.icon
        judge_name = self.grouping.judge.name
        print(f"  ⚖️ {judge_icon} {judge_name}：")

        debate_summary = self._build_debate_context()
        prompt = f"""【裁判裁决】
{debate_summary}

你是 {self.grouping.judge.icon} {self.grouping.judge.name}，请根据以上辩论给出最终裁决。

要求：
1. 总结正反双方的核心论点
2. 评价双方论点的说服力和逻辑性
3. 给出最终裁决：正方胜/反方胜/平局
4. 说明裁决理由
5. 给出对决策者的最终建议

请用300-500字完成裁决。"""
        ruling = await self._generate_speech(self.judge_agent, self.judge_model, prompt)
        return ruling

    def _build_debate_context(self) -> str:
        context_lines = [f"辩题：{self.topic}"]
        context_lines.append(f"正方立场：{self.pros_position}")
        context_lines.append(f"反方立场：{self.cons_position}")

        if self.background_qa:
            context_lines.append("")
            context_lines.append("用户背景信息：")
            for i, (q, a) in enumerate(zip(self.background_qa.questions, self.background_qa.answers), 1):
                context_lines.append(f"  {i}. {q}")
                context_lines.append(f"     回答：{a}")

        context_lines.append("")
        context_lines.append("辩论过程：")
        for i, speech in enumerate(self.speeches, 1):
            side_name = "正方" if speech.side == Side.PROS else "反方"
            context_lines.append(f"{i}. [{side_name} {speech.position}] {speech.speaker}：{speech.content}")
        return "\n".join(context_lines)

    def _print_speaker_label(
        self,
        icon: str,
        position: str,
        side: Side,
        step: Optional[int] = None,
        phase: Optional[Phase] = None,
    ) -> None:
        if step is not None:
            indicator = "○" if side == Side.PROS else "●"
            label = f"  {indicator} 第{step}步：{icon} {position}："
        elif phase == Phase.CLOSING:
            label = f"  ⚖️ {icon} {position}："
        else:
            label = f"  ⚖️ {icon} {position}："
        print(label)

    async def _generate_speech(
        self,
        agent: ReActAgent,
        model,
        extra_prompt: str,
        role_context: str | None = None,
    ) -> str:
        if self.streaming:
            return await self._generate_speech_streaming(agent, model, extra_prompt, role_context)
        else:
            msg = Msg("user", extra_prompt, "user")
            response = await agent(msg)
            return response.get_text_content() or ""

    async def _generate_speech_streaming(
        self,
        agent: ReActAgent,
        model,
        extra_prompt: str,
        role_context: str | None = None,
    ) -> str:
        sys_prompt = agent.sys_prompt
        if role_context:
            sys_prompt = f"{sys_prompt}\n\n【重要】你当前的辩手身份是：{role_context}。请始终以该身份发言。"

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": extra_prompt},
        ]

        content_parts: List[str] = []
        prev_len = 0
        async for chunk in await model(messages):
            if chunk:
                full_text = chunk.content[0].get("text", "") if chunk.content else ""
                if len(full_text) > prev_len:
                    new_text = full_text[prev_len:]
                    print(new_text, end="", flush=True)
                    content_parts.append(new_text)
                    prev_len = len(full_text)

        print()
        print()
        return "".join(content_parts)

    def _output_speech(
        self,
        speech: Speech,
        phase: Phase,
        step: Optional[int] = None,
    ) -> None:
        if self.streaming:
            pass
        else:
            self.ui.print_speech(speech.speaker, speech.content, speech.side, phase, step)
