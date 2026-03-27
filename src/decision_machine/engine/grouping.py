from typing import List
from agentscope.agent import ReActAgent
from agentscope.message import Msg

from ..types import Side, Phase, Persona, Team, GroupingResult, Speech
from ..agents import PERSONAS, AgentFactory


class GroupingEngine:

    def __init__(
        self,
        topic: str,
        pros_position: str,
        cons_position: str,
        factory: AgentFactory,
        ui,
    ):
        self.topic = topic
        self.pros_position = pros_position
        self.cons_position = cons_position
        self.factory = factory
        self.ui = ui

    async def run_grouping(self) -> tuple[GroupingResult, list[Speech]]:
        stances = await self._collect_stances()
        grouping = await self._determine_grouping(stances)
        return grouping, stances

    async def _collect_stances(self) -> List[Speech]:
        stances: List[Speech] = []

        for persona in PERSONAS:
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
            content = await self._stream_generate(agent, model, prompt)
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
        pros_keywords = ["支持正方", "赞成", "应该", "选择", "正方"]
        cons_keywords = ["支持反方", "反对", "不应该", "反方"]
        pros_count = sum(1 for kw in pros_keywords if kw in content)
        cons_count = sum(1 for kw in cons_keywords if kw in content)
        if pros_count > cons_count:
            return Side.PROS
        elif cons_count > pros_count:
            return Side.CONS
        else:
            return Side.NEUTRAL
    
    def _wrap_text(self, text: str, width: int) -> List[str]:
        """将长文本按宽度换行"""
        import unicodedata
        lines = []
        current_line = ""
        current_width = 0
        
        for char in text:
            char_width = 2 if unicodedata.east_asian_width(char) in ('F', 'W') else 1
            if current_width + char_width > width:
                if current_line:
                    lines.append(current_line)
                current_line = char
                current_width = char_width
            else:
                current_line += char
                current_width += char_width
        
        if current_line:
            lines.append(current_line)
        return lines if lines else [""]
    
    async def _stream_generate(self, agent: ReActAgent, model, prompt: str) -> str:
        """流式生成内容"""
        sys_prompt = agent.sys_prompt
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt},
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
        return "".join(content_parts)
    
    async def _determine_grouping(
        self,
        stances: list[Speech]
    ) -> GroupingResult:
        synthesizer = next(p for p in PERSONAS if p.name == "综合人格")
        debater_personas = [p for p in PERSONAS if p.name != "综合人格"]

        stance_summary = "\n".join([
            f"- {s.persona.icon} {s.persona.name}：{'支持正方' if s.side == Side.PROS else '支持反方' if s.side == Side.CONS else '中立'}"
            for s in stances
        ])
        debater_profiles = "\n".join([
            f"- {p.icon}{p.name}：{p.description}（决策倾向：{p.decision_bias}）"
            for p in debater_personas
        ])
        prompt = f"""【分组决策】
辩题：{self.topic}
正方立场：{self.pros_position}
反方立场：{self.cons_position}

四位辩手及其特点：
{debater_profiles}

各人初始表态（请结合其立场和性格特点综合考虑）：
{stance_summary}

{synthesizer.icon} {synthesizer.name}担任裁判，不参与辩论。
请根据每位辩手的性格特点和表态，决定正反两方的分组：
1. 正方需要2人（正方一辩负责立论，正方二辩补充）
2. 反方需要2人（反方一辩负责立论，反方二辩补充）
3. 综合人格只做裁判，不排入正方或反方

分组建议：
- 激进冒险型辩手适合正方，负责开篇立论、鼓舞士气
- 稳健保守型辩手适合反方，负责防守反击、以理服人
- 一辩通常由逻辑清晰、数据扎实的辩手担任
- 二辩可由情感丰富或补充进攻的辩手担任

        输出格式（只需输出JSON）：
{{
    "正方一辩": "人格名称",
    "正方二辩": "人格名称",
    "反方一辩": "人格名称",
    "反方二辩": "人格名称",
    "理由": "分组理由"
}}

只需输出JSON，不要有其他内容。"""

        judge_agent, _, judge_model = self.factory.create_judge(
            persona=synthesizer,
            topic=self.topic,
            pros_position=self.pros_position,
            cons_position=self.cons_position,
            stream=True,
        )
        
        print(f"    {synthesizer.icon} {synthesizer.name} 分析分组...")
        result_text = await self._stream_generate(judge_agent, judge_model, prompt)

        import json
        try:
            if "{" in result_text and "}" in result_text:
                start = result_text.find("{")
                end = result_text.rfind("}") + 1
                result = json.loads(result_text[start:end])
            else:
                result = self._parse_grouping_fallback(result_text)
        except Exception:
            result = self._parse_grouping_fallback(result_text)

        def find_persona(name: str) -> Persona:
            for p in debater_personas:
                if p.name in name:
                    return p
            return debater_personas[0]

        pros_first_name = result.get("正方一辩", "冒险人格")
        pros_second_name = result.get("正方二辩", "感性人格")
        cons_first_name = result.get("反方一辩", "理性人格")
        cons_second_name = result.get("反方二辩", "保守人格")

        if "综合人格" in [pros_first_name, pros_second_name, cons_first_name, cons_second_name]:
            if "冒险人格" not in [pros_first_name, pros_second_name, cons_first_name, cons_second_name]:
                pros_first_name = "冒险人格"
            elif "感性人格" not in [pros_first_name, pros_second_name, cons_first_name, cons_second_name]:
                pros_second_name = "感性人格"
            else:
                cons_first_name = "保守人格"

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
        reason = result.get("理由", "")

        print("  " + "━" * 50)
        print("    分组理由")
        print(f"  {reason}")
        print("  " + "━" * 50)
        print()

        return GroupingResult(
            pros_team=pros_team,
            cons_team=cons_team,
            judge=synthesizer,
            reason=reason,
        )

    def _parse_grouping_fallback(self, text: str) -> dict:
        return {
            "pros_first": "冒险人格",
            "pros_second": "感性人格",
            "cons_first": "保守人格",
            "cons_second": "理性人格",
            "reason": "默认分组",
        }
