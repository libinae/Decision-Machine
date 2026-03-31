import json

from agentscope.agent import ReActAgent

from ..agents import PERSONAS, AgentFactory
from ..constants import (
    GROUPING_KEYWORDS,
    JUDGE_PERSONA_NAME,
    PERSONA_CONSERVATIVE,
    PERSONA_EMPATHETIC,
    PERSONA_RATIONAL,
    PERSONA_RISK_TAKER,
)
from ..types import GroupingResult, Persona, Phase, Side, Speech, Team
from ..ui import StreamGenerator


class GroupingEngine:
    def __init__(
        self,
        topic: str,
        pros_position: str | None,
        cons_position: str | None,
        factory: AgentFactory,
        ui,
        stream_gen: StreamGenerator | None = None,
    ):
        self.topic = topic
        self.pros_position = pros_position
        self.cons_position = cons_position
        self.factory = factory
        self.ui = ui
        self.stream_gen = stream_gen or StreamGenerator(print_output=False)

    async def run_grouping(self) -> tuple[GroupingResult, list[Speech]]:
        # 如果没有提供正反方立场，先由 AI 分析
        if not self.pros_position or not self.cons_position:
            await self._analyze_positions()

        # 四位辩手表态（综合人格不参与）
        stances = await self._collect_stances()

        # 综合人格进行分组
        grouping = await self._determine_grouping(stances)
        return grouping, stances

    async def _analyze_positions(self) -> None:
        """让综合人格分析辩题，确定正反方立场（输出分析结果）"""
        synthesizer = next(p for p in PERSONAS if p.name == JUDGE_PERSONA_NAME)

        print(f"    {synthesizer.icon} {synthesizer.name} 分析辩题...")
        print()

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

        result_text = await self._stream_generate_print(judge_agent, judge_model, prompt)
        print()

        # 解析正反方立场
        try:
            if "【正方】" in result_text and "【反方】" in result_text:
                # 从标记中提取
                pros_start = result_text.find("【正方】") + 4
                pros_end = result_text.find("【反方】", pros_start)
                self.pros_position = result_text[pros_start:pros_end].strip()

                cons_start = result_text.find("【反方】") + 4
                # 找到反方内容的结束位置（下一个标记或文本结束）
                cons_end = result_text.find("\n", cons_start)
                if cons_end == -1:
                    cons_end = len(result_text)
                self.cons_position = result_text[cons_start:cons_end].strip()
        except Exception:
            pass

        # 后备方案：JSON解析或文本分割
        if not self.pros_position or not self.cons_position:
            try:
                if "{" in result_text and "}" in result_text:
                    start = result_text.find("{")
                    end = result_text.rfind("}") + 1
                    result = json.loads(result_text[start:end])
                    self.pros_position = result.get("正方", "")
                    self.cons_position = result.get("反方", "")
            except (json.JSONDecodeError, Exception):
                pass

        if not self.pros_position or not self.cons_position:
            self._fallback_parse_topic()

    def _fallback_parse_topic(self) -> None:
        """后备方案：简单的文本分割"""
        clean_topic = self.topic.replace("我应该", "").replace("我要", "").replace("我", "").strip()
        separators = ["还是", " vs ", " VS ", " versus ", "或者", "或"]

        for sep in separators:
            if sep in clean_topic:
                parts = clean_topic.split(sep)
                self.pros_position = parts[0].strip().replace("？", "").replace("?", "")
                self.cons_position = (
                    parts[1].strip().replace("？", "").replace("?", "")
                    if len(parts) > 1
                    else f"不{self.pros_position}"
                )
                return

        self.pros_position = clean_topic
        self.cons_position = f"不{clean_topic}"

    async def _collect_stances(self) -> list[Speech]:
        """四位辩手表态（综合人格不参与）"""
        stances: list[Speech] = []

        # 只让四位辩手表态，综合人格跳过
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
            prompt = f"""【表态环节】
辩题：{self.topic}
正方立场：{self.pros_position}
反方立场：{self.cons_position}

作为 {persona.icon} {persona.name}，请表达你对这个问题的看法：
1. 你的第一反应是什么？
2. 你倾向于支持正方还是反方？
3. 简要说明你的理由。

保持人格特点，150-200字即可。"""

            print(f"    {persona.icon} {persona.name}：")
            content = await self._stream_generate_print(agent, model, prompt)
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
            print()
        return stances

    def _infer_side(self, content: str) -> Side:
        pros_keywords = GROUPING_KEYWORDS["pros"]
        cons_keywords = GROUPING_KEYWORDS["cons"]
        pros_count = sum(1 for kw in pros_keywords if kw in content)
        cons_count = sum(1 for kw in cons_keywords if kw in content)
        if pros_count > cons_count:
            return Side.PROS
        elif cons_count > pros_count:
            return Side.CONS
        else:
            return Side.NEUTRAL

    async def _stream_generate(self, agent: ReActAgent, model, prompt: str) -> str:
        """静默生成（不输出到终端）"""
        # 直接调用 agent，不使用流式
        from agentscope.message import Msg

        msg = Msg("user", prompt, "user")
        response = await agent(msg)
        return response.get_text_content() or ""

    async def _stream_generate_print(self, agent: ReActAgent, model, prompt: str) -> str:
        """流式生成并输出到终端"""
        self.stream_gen.print_output = True
        result = await self.stream_gen.generate(agent, model, prompt)
        self.stream_gen.print_output = False
        return result

    async def _determine_grouping(self, stances: list[Speech]) -> GroupingResult:
        """综合人格进行分组并输出理由"""
        synthesizer = next(p for p in PERSONAS if p.name == JUDGE_PERSONA_NAME)
        debater_personas = [p for p in PERSONAS if p.name != JUDGE_PERSONA_NAME]

        stance_summary = "\n".join(
            [
                f"- {s.persona.icon} {s.persona.name}：{'支持正方' if s.side == Side.PROS else '支持反方' if s.side == Side.CONS else '中立'}"
                for s in stances
            ]
        )
        debater_profiles = "\n".join(
            [f"- {p.icon}{p.name}：{p.description}" for p in debater_personas]
        )

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

        print(f"    {synthesizer.icon} {synthesizer.name} 分组分析：")
        print()
        result_text = await self._stream_generate_print(judge_agent, judge_model, prompt)
        print()

        # 解析分组结果
        result = {}
        reason = ""
        try:
            # 提取分组信息
            if "【分组】" in result_text:
                grouping_start = result_text.find("【分组】") + 4
                grouping_end = result_text.find("【理由】", grouping_start)
                if grouping_end == -1:
                    grouping_end = len(result_text)
                grouping_text = result_text[grouping_start:grouping_end]

                # 解析各辩手
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

            # 提取理由
            if "【理由】" in result_text:
                reason_start = result_text.find("【理由】") + 4
                reason = result_text[reason_start:].strip()
        except Exception:
            pass

        # 后备：尝试JSON解析
        if not result:
            try:
                if "{" in result_text and "}" in result_text:
                    start = result_text.find("{")
                    end = result_text.rfind("}") + 1
                    result = json.loads(result_text[start:end])
            except (json.JSONDecodeError, Exception):
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

        # 确保综合人格不被分配到辩手位置
        if JUDGE_PERSONA_NAME in [
            pros_first_name,
            pros_second_name,
            cons_first_name,
            cons_second_name,
        ]:
            if PERSONA_RISK_TAKER not in [
                pros_first_name,
                pros_second_name,
                cons_first_name,
                cons_second_name,
            ]:
                pros_first_name = PERSONA_RISK_TAKER
            elif PERSONA_EMPATHETIC not in [
                pros_first_name,
                pros_second_name,
                cons_first_name,
                cons_second_name,
            ]:
                pros_second_name = PERSONA_EMPATHETIC
            else:
                cons_first_name = PERSONA_CONSERVATIVE

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
