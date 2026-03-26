from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel

from ..types import Persona, BackgroundQA
from ..config import AppConfig


class AgentFactory:

    def __init__(self, config: AppConfig | None = None, streaming: bool = False):
        self.config = config or AppConfig.from_env()
        self.streaming = streaming

    def _create_model(self, stream: bool = False) -> DashScopeChatModel:
        model_name = self.config.model.model_name
        generate_kwargs = {}
        multimodality = False
        if "qwen3.5" in model_name:
            generate_kwargs["incremental_output"] = True
            generate_kwargs["enable_thinking"] = False
            multimodality = True
        return DashScopeChatModel(
            model_name=model_name,
            api_key=self.config.model.api_key,
            stream=stream,
            generate_kwargs=generate_kwargs,
            multimodality=multimodality,
        )

    def _create_agent(self, name: str, prompt: str, stream: bool = False) -> ReActAgent:
        agent = ReActAgent(
            name=name,
            sys_prompt=prompt,
            model=self._create_model(stream=stream),
            formatter=DashScopeChatFormatter(),
        )
        agent.set_console_output_enabled(False)
        return agent

    def _format_bg_qa(self, qa: BackgroundQA | None) -> str:
        if qa is None:
            return ""
        lines = ["用户背景信息："]
        for i, (q, a) in enumerate(zip(qa.questions, qa.answers), 1):
            lines.append(f"{i}. {q}")
            lines.append(f"   用户回答：{a}")
        return "\n".join(lines)

    def create_debater(
        self,
        persona: Persona,
        topic: str,
        pros_position: str,
        cons_position: str,
        side: str = "pros",
        background_qa: BackgroundQA | None = None,
        stream: bool | None = None,
    ) -> tuple[ReActAgent, Msg, DashScopeChatModel]:
        prompt = persona.prompt_template.format(
            icon=persona.icon,
            topic=topic,
            pros_position=pros_position,
            cons_position=cons_position,
        )
        bg_context = self._format_bg_qa(background_qa)
        if bg_context:
            prompt = f"{prompt}\n\n【用户背景信息】\n{bg_context}\n\n辩手应根据以上背景信息，有针对性地展开辩论，结合用户的实际情况提出具体建议。"

        use_stream = stream if stream is not None else self.streaming
        agent = self._create_agent(f"{persona.icon} {persona.name}", prompt, stream=use_stream)
        model = self._create_model(stream=use_stream)

        if side == "pros":
            instruction = f"你坚定支持【{pros_position}】。请发表你的开场陈词，表明你的立场。"
        elif side == "cons":
            instruction = f"你坚定支持【{cons_position}】。请发表你的开场陈词，表明你的立场。"
        else:
            instruction = "请客观分析当前辩论情况，给出你的判断。"

        initial_msg = Msg("system", instruction, "system")
        return agent, initial_msg, model

    def create_judge(
        self,
        persona: Persona,
        topic: str,
        pros_position: str,
        cons_position: str,
        stream: bool | None = None,
    ) -> tuple[ReActAgent, Msg, DashScopeChatModel]:
        judge_prompt = f"""你是一场辩论的【裁判】{persona.icon} {persona.name}。

你的职责：
- 保持客观中立，平衡全局
- 认真听取双方观点
- 分析论点的逻辑性和说服力
- 最终给出裁决，说明理由

当前辩题：{topic}
正方立场：{pros_position}
反方立场：{cons_position}

请注意：你将看到完整的辩论过程，请根据双方表现给出公正评判。"""

        use_stream = stream if stream is not None else self.streaming
        agent = self._create_agent(f"⚖️ {persona.name}", judge_prompt, stream=use_stream)
        model = self._create_model(stream=use_stream)
        initial_msg = Msg(
            "system",
            "请等待辩论结束后，根据双方表现给出裁决。",
            "system"
        )
        return agent, initial_msg, model
