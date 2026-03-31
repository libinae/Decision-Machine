from dataclasses import dataclass
from typing import Any

from agentscope.agent import ReActAgent

from ..types import BackgroundQA, GroupingResult, Phase, Side, Speech
from ..ui import StreamGenerator, TerminalUI


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
        pros_first_model: Any,
        pros_second_model: Any,
        cons_first_model: Any,
        cons_second_model: Any,
        judge_model: Any,
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
        self.speeches: list[Speech] = []
        self.stream_gen = StreamGenerator()

    async def run_opening_statements(self) -> OpeningResult:
        self.ui.print_phase("正式辩论 - 开篇陈词")

        order = [
            (
                self.pros_first_agent,
                self.pros_first_model,
                Side.PROS,
                self.grouping.pros_team.first_debater,
                "正方一辩",
                1,
            ),
            (
                self.cons_first_agent,
                self.cons_first_model,
                Side.CONS,
                self.grouping.cons_team.first_debater,
                "反方一辩",
                2,
            ),
            (
                self.cons_second_agent,
                self.cons_second_model,
                Side.CONS,
                self.grouping.cons_team.second_debater,
                "反方二辩",
                3,
            ),
            (
                self.pros_second_agent,
                self.pros_second_model,
                Side.PROS,
                self.grouping.pros_team.second_debater,
                "正方二辩",
                4,
            ),
        ]

        results: list[Speech] = []
        for agent, model, side, persona, position, step in order:
            self._print_speaker_label(persona.icon, position, side, step=step)

            # 构建更明确的开篇提示
            if side == Side.PROS:
                my_position = self.pros_position
                opponent_position = self.cons_position
            else:
                my_position = self.cons_position
                opponent_position = self.pros_position

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

            content = await self._generate_speech(agent, model, prompt, role_context=position)
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

    async def run_free_debate(self) -> list[Speech]:
        self.ui.print_phase("正式辩论 - 自由辩论")

        debate_agents = [
            (
                self.pros_first_agent,
                self.pros_first_model,
                Side.PROS,
                self.grouping.pros_team.first_debater,
                "正方一辩",
            ),
            (
                self.cons_first_agent,
                self.cons_first_model,
                Side.CONS,
                self.grouping.cons_team.first_debater,
                "反方一辩",
            ),
            (
                self.cons_second_agent,
                self.cons_second_model,
                Side.CONS,
                self.grouping.cons_team.second_debater,
                "反方二辩",
            ),
            (
                self.pros_second_agent,
                self.pros_second_model,
                Side.PROS,
                self.grouping.pros_team.second_debater,
                "正方二辩",
            ),
        ]
        current_idx = 0
        for round_num in range(1, self.max_rounds + 1):
            agent, model, side, persona, position = debate_agents[current_idx]

            # 构建更精简的上下文
            recent_speeches = self.speeches[-6:] if len(self.speeches) > 6 else self.speeches
            context_lines = []
            for speech in recent_speeches:
                side_name = "正" if speech.side == Side.PROS else "反"
                context_lines.append(f"[{side_name}]{speech.speaker}：{speech.content[:100]}...")

            context = "\n".join(context_lines)

            # 确定立场
            if side == Side.PROS:
                my_position = self.pros_position
                opponent_side = "反方"
            else:
                my_position = self.cons_position
                opponent_side = "正方"

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

        # 构建精简的辩论总结
        recent_speeches = self.speeches[-8:] if len(self.speeches) > 8 else self.speeches
        context_lines = []
        for speech in recent_speeches:
            side_name = "正" if speech.side == Side.PROS else "反"
            context_lines.append(f"[{side_name}]{speech.speaker}：{speech.content[:80]}...")
        context = "\n".join(context_lines)

        # 正方结辩
        pros_prompt = f"""【正方结辩】

你是 正方一辩（{self.grouping.pros_team.first_debater.icon} {self.grouping.pros_team.first_debater.name}）。
你支持：【{self.pros_position}】

【辩论回顾】
{context}

【你的任务】
作为正方最后陈述，请：
1. 总结正方的核心论点
2. 指出反方论点的漏洞
3. 再次强调你的立场价值
4. 保持你的人格特点

150字左右，直接发言："""

        self._print_speaker_label(
            self.grouping.pros_team.first_debater.icon,
            "正方一辩",
            Side.PROS,
        )
        pros_content = await self._generate_speech(
            self.pros_first_agent,
            self.pros_first_model,
            pros_prompt,
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

        # 反方结辩
        cons_prompt = f"""【反方结辩】

你是 反方一辩（{self.grouping.cons_team.first_debater.icon} {self.grouping.cons_team.first_debater.name}）。
你支持：【{self.cons_position}】

【辩论回顾】
{context}

【你的任务】
作为反方最后陈述，请：
1. 总结反方的核心论点
2. 指出正方论点的漏洞
3. 再次强调你的立场价值
4. 保持你的人格特点

150字左右，直接发言："""

        self._print_speaker_label(
            self.grouping.cons_team.first_debater.icon,
            "反方一辩",
            Side.CONS,
        )
        cons_content = await self._generate_speech(
            self.cons_first_agent,
            self.cons_first_model,
            cons_prompt,
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
        self._print_speaker_label(judge_icon, judge_name, Side.NEUTRAL, is_judge=True)

        # 构建完整的辩论记录
        all_speeches = []
        for speech in self.speeches:
            side_name = "正方" if speech.side == Side.PROS else "反方"
            all_speeches.append(f"[{side_name}-{speech.position}]{speech.speaker}：{speech.content}")

        debate_record = "\n".join(all_speeches)

        prompt = f"""【裁判裁决】

你是裁判（{judge_icon} {judge_name}）。

辩题：{self.topic}
正方立场：{self.pros_position}
反方立场：{self.cons_position}

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

        ruling = await self._generate_speech(self.judge_agent, self.judge_model, prompt)
        return ruling

    def _print_speaker_label(
        self,
        icon: str,
        position: str,
        side: Side,
        step: int | None = None,
        phase: Phase | None = None,
        is_judge: bool = False,
    ) -> None:
        if is_judge:
            # 裁判使用天平符号
            label = f"  ⚖️ {icon} {position}："
        elif step is not None:
            # 自由辩论使用正反方符号和步数
            indicator = "○" if side == Side.PROS else "●"
            label = f"  {indicator} 第{step}步：{icon} {position}："
        else:
            # 开篇和结辩使用正反方符号
            indicator = "○" if side == Side.PROS else "●"
            label = f"  {indicator} {icon} {position}："
        print(label)

    async def _generate_speech(
        self,
        agent: ReActAgent,
        model: Any,
        extra_prompt: str,
        role_context: str | None = None,
    ) -> str:
        if self.streaming:
            return await self._generate_speech_streaming(agent, model, extra_prompt, role_context)
        else:
            return await self.stream_gen.generate_non_stream(agent, extra_prompt)

    async def _generate_speech_streaming(
        self,
        agent: ReActAgent,
        model: Any,
        extra_prompt: str,
        role_context: str | None = None,
    ) -> str:
        sys_prompt = agent.sys_prompt
        if role_context:
            sys_prompt = (
                f"{sys_prompt}\n\n【重要】你当前的辩手身份是：{role_context}。请始终以该身份发言。"
            )

        return await self.stream_gen.generate(
            agent, model, extra_prompt, sys_prompt_override=sys_prompt
        )

    def _output_speech(
        self,
        speech: Speech,
        phase: Phase,
        step: int | None = None,
    ) -> None:
        if self.streaming:
            pass
        else:
            self.ui.print_speech(speech.speaker, speech.content, speech.side, phase, step)
