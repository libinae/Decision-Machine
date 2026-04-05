"""SSE 流式路由 - HTTP API + SSE 替代 WebSocket

适配阿里云函数计算环境
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# 添加项目路径
project_root = Path(__file__).resolve().parents[2] / "src"
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from web.api.task_manager import generate_task_id, get_task_manager, TaskManager

router = APIRouter()


# ========== 数据模型 ==========

class StartRequest(BaseModel):
    topic: str


class AnswerRequest(BaseModel):
    num: int
    answer: str


# ========== 任务存储 ==========

# 运行中的任务（用于本地开发，函数计算需要用 OSS）
_running_tasks: dict[str, asyncio.Task] = {}


# ========== API 路由 ==========

@router.post("/api/start")
async def start_debate(request: StartRequest):
    """启动辩论任务，返回任务ID"""
    topic = request.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="辩题不能为空")

    task_id = generate_task_id()
    manager = get_task_manager(task_id)

    # 初始化任务状态
    await manager.save_state({
        "topic": topic,
        "status": "init",
        "phase": "init",
        "message_seq": 0,
        "answers": {},
    })

    # 推送初始消息
    await manager.push_message("header", {"topic": topic})
    await manager.push_message("phase", {"name": "🚀 正在启动辩论..."})

    # 异步启动辩论流程
    task = asyncio.create_task(run_debate(task_id, topic, manager))
    _running_tasks[task_id] = task

    return {"task_id": task_id}


@router.get("/api/stream/{task_id}")
async def stream_debate(task_id: str):
    """SSE 流式输出辩论过程"""
    manager = get_task_manager(task_id)

    # 验证任务存在
    state = await manager.load_state()
    if not state:
        raise HTTPException(status_code=404, detail="任务不存在")

    async def event_generator():
        """SSE 事件生成器"""
        last_seq = 0
        last_ping = 0

        while True:
            try:
                # 加载任务状态
                state = await manager.load_state()

                # 检查任务状态
                if state.get("status") == "complete":
                    yield f"event: complete\ndata: {json.dumps({'winner': state.get('winner')})}\n\n"
                    break

                # 检查等待问答状态
                if state.get("status") == "waiting_answer":
                    q_num = state.get("waiting_question_num", 0)
                    q_text = state.get("waiting_question", "")
                    yield f"event: qa\ndata: {json.dumps({'num': q_num, 'question': q_text})}\n\n"

                # 加载并推送新消息
                messages = await manager.load_messages(since_seq=last_seq)
                for msg in messages:
                    last_seq = msg.get("seq", last_seq)
                    yield f"data: {json.dumps(msg)}\n\n"

                # 定期发送心跳
                now = asyncio.get_event_loop().time()
                if now - last_ping > 5:
                    yield f": heartbeat\n\n"
                    last_ping = now

                await asyncio.sleep(0.3)

            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/api/state/{task_id}")
async def get_task_state(task_id: str):
    """获取任务当前状态（用于轮询）"""
    manager = get_task_manager(task_id)
    state = await manager.load_state()
    if not state:
        raise HTTPException(status_code=404, detail="任务不存在")
    return state


@router.post("/api/answer/{task_id}")
async def submit_answer(task_id: str, request: AnswerRequest):
    """提交用户回答"""
    manager = get_task_manager(task_id)
    state = await manager.load_state()
    if not state:
        raise HTTPException(status_code=404, detail="任务不存在")

    if state.get("status") != "waiting_answer":
        raise HTTPException(status_code=400, detail="当前不在问答阶段")

    await manager.save_answer(request.num, request.answer)
    return {"status": "ok", "num": request.num}


@router.get("/api/report/{task_id}")
async def get_report(task_id: str):
    """获取辩论报告"""
    manager = get_task_manager(task_id)
    state = await manager.load_state()
    if not state or state.get("status") != "complete":
        raise HTTPException(status_code=404, detail="报告未生成")

    # 从状态中获取报告内容
    report = state.get("report", "")
    return {"report": report}


# ========== 辩论流程 ==========

async def run_debate(task_id: str, topic: str, manager: TaskManager):
    """异步运行辩论流程"""
    try:
        # 动态导入核心模块
        from dotenv import load_dotenv
        env_path = Path(__file__).resolve().parents[2] / ".env"
        load_dotenv(env_path)

        from decision_machine.agents import PERSONAS, AgentFactory
        from decision_machine.config import AppConfig
        from decision_machine.constants import DEFAULT_BACKGROUND_QUESTIONS
        from decision_machine.engine.grouping import GroupingEngine
        from decision_machine.types import BackgroundQA, Phase, Side, Speech

        config = AppConfig.from_env()
        factory = AgentFactory(config, streaming=False)

        # ===== 阶段一：初始化人格 =====
        await manager.push_message("phase", {"name": "🎭 初始化五重人格"})
        for persona in PERSONAS:
            await manager.push_message("persona_init", {
                "name": persona.name,
                "icon": persona.icon,
                "success": True
            })
            await asyncio.sleep(0.1)

        # ===== 阶段二：分组 =====
        await manager.push_message("phase", {"name": "🗣️ 讨论与分组"})

        # 使用简化的分组逻辑（函数计算环境下避免复杂依赖）
        grouping_result = await simple_grouping(topic, manager, factory)

        # ===== 阶段三：背景问答 =====
        await manager.push_message("phase", {"name": "📝 背景信息收集"})
        await manager.push_message("qa_intro", {})

        questions = DEFAULT_BACKGROUND_QUESTIONS[:5]
        answers: list[str] = []

        for i, q in enumerate(questions, 1):
            # 设置等待状态
            await manager.set_waiting_answer(i, q)

            # 等待用户回答（轮询检测）
            answer = await wait_for_answer(manager, i, timeout=120)
            answers.append(answer if answer else "（未回答）")

        background_qa = BackgroundQA(questions=questions, answers=answers)

        # ===== 阶段四：开篇陈词 =====
        await manager.push_message("phase", {"name": "🎤 开篇陈词"})

        # 创建辩手并生成开篇陈词
        await generate_opening_statements(topic, grouping_result, background_qa, manager, factory)

        # ===== 阶段五：自由辩论 =====
        await manager.push_message("phase", {"name": "💬 自由辩论"})
        await generate_free_debate(topic, grouping_result, manager, factory, config, rounds=5)

        # ===== 阶段六：结辩 =====
        await manager.push_message("phase", {"name": "🏁 结辩陈词"})
        await generate_closing_statements(topic, grouping_result, manager, factory)

        # ===== 阶段七：裁决 =====
        await manager.push_message("phase", {"name": "⚖️ 裁判裁决"})
        ruling = await generate_ruling(topic, grouping_result, manager, factory)

        # ===== 完成 =====
        winner = "draw"  # 简化：不判断胜方
        state = await manager.load_state()
        state["status"] = "complete"
        state["winner"] = winner
        state["ruling"] = ruling
        await manager.save_state(state)

        await manager.push_message("complete", {"winner": winner})

    except Exception as e:
        await manager.push_message("error", {"message": str(e)})
        state = await manager.load_state()
        state["status"] = "error"
        state["error"] = str(e)
        await manager.save_state(state)


async def wait_for_answer(manager: TaskManager, question_num: int, timeout: int = 120) -> str:
    """等待用户回答"""
    start_time = asyncio.get_event_loop().time()
    while True:
        answer = await manager.get_answer(question_num)
        if answer:
            return answer

        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > timeout:
            return "（超时未回答）"

        await asyncio.sleep(1)


async def simple_grouping(topic: str, manager: TaskManager, factory):
    """简化分组逻辑"""
    from decision_machine.agents import PERSONAS
    from decision_machine.types import GroupingResult, Persona, Side, Team

    # 默认分组
    pros_team = Team(
        side=Side.PROS,
        first_debater=PERSONAS[0],  # 冒险人格
        second_debater=PERSONAS[2],  # 感性人格
    )
    cons_team = Team(
        side=Side.CONS,
        first_debater=PERSONAS[3],  # 理性人格
        second_debater=PERSONAS[1],  # 保守人格
    )

    # 简化立场提取
    pros_position = "支持改变/行动"
    cons_position = "保持现状/谨慎"

    result = GroupingResult(
        pros_team=pros_team,
        cons_team=cons_team,
        judge=PERSONAS[4],
        pros_position=pros_position,
        cons_position=cons_position,
        reason="基于人格特点自动分配",
    )

    await manager.push_message("grouping", {
        "pros_position": pros_position,
        "cons_position": cons_position,
        "pros_team": {
            "first": {"name": pros_team.first_debater.name, "icon": pros_team.first_debater.icon},
            "second": {"name": pros_team.second_debater.name, "icon": pros_team.second_debater.icon},
        },
        "cons_team": {
            "first": {"name": cons_team.first_debater.name, "icon": cons_team.first_debater.icon},
            "second": {"name": cons_team.second_debater.name, "icon": cons_team.second_debater.icon},
        },
        "judge": {"name": PERSONAS[4].name, "icon": PERSONAS[4].icon},
    })

    return result


async def generate_opening_statements(topic, grouping, background_qa, manager, factory):
    """生成开篇陈词"""
    from agentscope.message import Msg

    debaters = [
        (grouping.pros_team.first_debater, "pros", "正方一辩", grouping.pros_position),
        (grouping.cons_team.first_debater, "cons", "反方一辩", grouping.cons_position),
        (grouping.cons_team.second_debater, "cons", "反方二辩", grouping.cons_position),
        (grouping.pros_team.second_debater, "pros", "正方二辩", grouping.pros_position),
    ]

    for persona, side, position, stance in debaters:
        agent, _, _ = factory.create_debater(
            persona=persona,
            topic=topic,
            pros_position=grouping.pros_position,
            cons_position=grouping.cons_position,
            side=side,
            background_qa=background_qa,
            stream=False,
        )

        prompt = f"""【开篇陈词】
你是 {position}（{persona.icon} {persona.name}）。
你支持：【{stance}】

请发表你的开篇陈词（200-300字）：
1. 明确表明立场
2. 提出2-3个核心论点
3. 用你的人格特点论证

直接发言："""

        await manager.push_message("speech_start", {
            "speaker": f"{persona.icon} {persona.name}",
            "position": position,
            "side": side,
        })

        msg = Msg("user", prompt, "user")
        response = await agent(msg)
        content = response.get_text_content() or ""

        await manager.push_message("speech", {
            "speaker": f"{persona.icon} {persona.name}",
            "content": content,
            "side": side,
        })


async def generate_free_debate(topic, grouping, manager, factory, config, rounds=5):
    """生成自由辩论"""
    from agentscope.message import Msg

    debaters = [
        (grouping.pros_team.first_debater, "pros", "正方一辩"),
        (grouping.cons_team.first_debater, "cons", "反方一辩"),
        (grouping.cons_team.second_debater, "cons", "反方二辩"),
        (grouping.pros_team.second_debater, "pros", "正方二辩"),
    ]

    for round_num in range(1, rounds + 1):
        persona, side, position = debaters[round_num % 4]
        stance = grouping.pros_position if side == "pros" else grouping.cons_position

        agent, _, _ = factory.create_debater(
            persona=persona,
            topic=topic,
            pros_position=grouping.pros_position,
            cons_position=grouping.cons_position,
            side=side,
            stream=False,
        )

        prompt = f"""【第{round_num}轮自由辩论】
你是 {position}（{persona.icon} {persona.name}）。
你支持：【{stance}】

针对对手论点进行反驳（150字左右），保持你的人格特点。

直接发言："""

        await manager.push_message("speech_start", {
            "speaker": f"{persona.icon} {persona.name}",
            "position": f"第{round_num}轮 {position}",
            "side": side,
            "round": round_num,
        })

        msg = Msg("user", prompt, "user")
        response = await agent(msg)
        content = response.get_text_content() or ""

        await manager.push_message("speech", {
            "speaker": f"{persona.icon} {persona.name}",
            "content": content,
            "side": side,
        })


async def generate_closing_statements(topic, grouping, manager, factory):
    """生成结辩陈词"""
    from agentscope.message import Msg

    # 正方结辩
    persona = grouping.pros_team.first_debater
    agent, _, _ = factory.create_debater(
        persona=persona,
        topic=topic,
        pros_position=grouping.pros_position,
        cons_position=grouping.cons_position,
        side="pros",
        stream=False,
    )

    prompt = f"""【正方结辩】
你是 正方一辩（{persona.icon} {persona.name}）。
你支持：【{grouping.pros_position}】

总结正方核心论点，强调立场价值（150字左右）。

直接发言："""

    await manager.push_message("speech_start", {
        "speaker": f"{persona.icon} {persona.name}",
        "position": "正方结辩",
        "side": "pros",
    })

    msg = Msg("user", prompt, "user")
    response = await agent(msg)
    content = response.get_text_content() or ""

    await manager.push_message("speech", {
        "speaker": f"{persona.icon} {persona.name}",
        "content": content,
        "side": "pros",
    })

    # 反方结辩
    persona = grouping.cons_team.first_debater
    agent, _, _ = factory.create_debater(
        persona=persona,
        topic=topic,
        pros_position=grouping.pros_position,
        cons_position=grouping.cons_position,
        side="cons",
        stream=False,
    )

    prompt = f"""【反方结辩】
你是 反方一辩（{persona.icon} {persona.name}）。
你支持：【{grouping.cons_position}】

总结反方核心论点，强调立场价值（150字左右）。

直接发言："""

    await manager.push_message("speech_start", {
        "speaker": f"{persona.icon} {persona.name}",
        "position": "反方结辩",
        "side": "cons",
    })

    msg = Msg("user", prompt, "user")
    response = await agent(msg)
    content = response.get_text_content() or ""

    await manager.push_message("speech", {
        "speaker": f"{persona.icon} {persona.name}",
        "content": content,
        "side": "cons",
    })


async def generate_ruling(topic, grouping, manager, factory):
    """生成裁判裁决"""
    from agentscope.message import Msg

    judge_persona = grouping.judge
    agent, _, _ = factory.create_judge(
        persona=judge_persona,
        topic=topic,
        pros_position=grouping.pros_position,
        cons_position=grouping.cons_position,
        stream=False,
    )

    prompt = f"""【裁判裁决】
你是裁判（{judge_persona.icon} {judge_persona.name}）。

辩题：{topic}
正方立场：{grouping.pros_position}
反方立场：{grouping.cons_position}

请给出裁决：
1. 正方核心论点总结（2-3条）
2. 反方核心论点总结（2-3条）
3. 最终裁决：正方胜 / 反方胜 / 平局
4. 给决策者的建议

请裁决："""

    await manager.push_message("speech_start", {
        "speaker": f"{judge_persona.icon} {judge_persona.name}",
        "position": "裁判",
        "side": "judge",
    })

    msg = Msg("user", prompt, "user")
    response = await agent(msg)
    ruling = response.get_text_content() or ""

    await manager.push_message("ruling", {"content": ruling})
    await manager.push_message("winner", {"winner": "draw"})

    return ruling