"""任务状态管理模块

使用阿里云 OSS 存储任务状态和消息队列，适配函数计算无状态特性
"""

import json
import os
import time
import uuid
from typing import Any

try:
    import oss2
    HAS_OSS = True
except ImportError:
    HAS_OSS = False

# OSS 配置（从环境变量读取）
OSS_ACCESS_KEY_ID = os.getenv("OSS_ACCESS_KEY_ID", "")
OSS_ACCESS_KEY_SECRET = os.getenv("OSS_ACCESS_KEY_SECRET", "")
OSS_ENDPOINT = os.getenv("OSS_ENDPOINT", "oss-cn-hangzhou.aliyuncs.com")
OSS_BUCKET_NAME = os.getenv("OSS_BUCKET_NAME", "decision-machine-state")

# 本地开发时使用内存存储
_local_storage: dict[str, dict] = {}


def get_oss_bucket():
    """获取 OSS Bucket 实例"""
    if not HAS_OSS or not OSS_ACCESS_KEY_ID:
        return None
    auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
    bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET_NAME)
    return bucket


def generate_task_id() -> str:
    """生成唯一任务 ID"""
    return f"task_{uuid.uuid4().hex[:12]}_{int(time.time())}"


class TaskManager:
    """任务状态管理器"""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.bucket = get_oss_bucket()
        self._use_local = self.bucket is None

    async def save_state(self, state: dict) -> None:
        """保存任务状态"""
        path = f"{self.task_id}/state.json"
        state["updated_at"] = time.time()
        if self._use_local:
            _local_storage[path] = state
        else:
            self.bucket.put_object(path, json.dumps(state).encode())

    async def load_state(self) -> dict:
        """加载任务状态"""
        path = f"{self.task_id}/state.json"
        if self._use_local:
            return _local_storage.get(path, {})
        try:
            result = self.bucket.get_object(path)
            return json.loads(result.read().decode())
        except oss2.exceptions.NoSuchKey:
            return {}

    async def push_message(self, msg_type: str, data: Any) -> int:
        """推送消息到队列，返回序列号"""
        state = await self.load_state()
        seq = state.get("message_seq", 0) + 1
        state["message_seq"] = seq
        await self.save_state(state)

        path = f"{self.task_id}/messages/{seq:04d}.json"
        msg = {"type": msg_type, "data": data, "seq": seq, "time": time.time()}
        if self._use_local:
            _local_storage[path] = msg
        else:
            self.bucket.put_object(path, json.dumps(msg).encode())
        return seq

    async def load_messages(self, since_seq: int = 0) -> list[dict]:
        """加载消息队列（从指定序列号之后）"""
        if self._use_local:
            messages = []
            for key, value in _local_storage.items():
                if key.startswith(f"{self.task_id}/messages/") and value.get("seq", 0) > since_seq:
                    messages.append(value)
            return sorted(messages, key=lambda x: x.get("seq", 0))

        # OSS 列表查询
        prefix = f"{self.task_id}/messages/"
        messages = []
        for obj in oss2.ObjectIterator(self.bucket, prefix=prefix):
            try:
                result = self.bucket.get_object(obj.key)
                msg = json.loads(result.read().decode())
                if msg.get("seq", 0) > since_seq:
                    messages.append(msg)
            except Exception:
                pass
        return sorted(messages, key=lambda x: x.get("seq", 0))

    async def save_answer(self, question_num: int, answer: str) -> None:
        """保存用户回答"""
        state = await self.load_state()
        answers = state.get("answers", {})
        answers[str(question_num)] = answer
        state["answers"] = answers
        state["status"] = "running"  # 恢复运行状态
        await self.save_state(state)

        # 推送回答消息
        await self.push_message("answer_received", {"num": question_num, "answer": answer})

    async def get_answer(self, question_num: int) -> str | None:
        """获取用户回答"""
        state = await self.load_state()
        answers = state.get("answers", {})
        return answers.get(str(question_num))

    async def set_waiting_answer(self, question_num: int, question: str) -> None:
        """设置等待用户回答状态"""
        state = await self.load_state()
        state["status"] = "waiting_answer"
        state["waiting_question_num"] = question_num
        state["waiting_question"] = question
        await self.save_state(state)

        # 推送问答消息
        await self.push_message("qa_question", {"num": question_num, "question": question})

    async def clear_task(self) -> None:
        """清理任务数据"""
        if self._use_local:
            keys_to_delete = [k for k in _local_storage if k.startswith(f"{self.task_id}/")]
            for k in keys_to_delete:
                del _local_storage[k]
        else:
            prefix = f"{self.task_id}/"
            for obj in oss2.ObjectIterator(self.bucket, prefix=prefix):
                self.bucket.delete_object(obj.key)


# 全局任务管理器缓存
_task_managers: dict[str, TaskManager] = {}


def get_task_manager(task_id: str) -> TaskManager:
    """获取任务管理器实例"""
    if task_id not in _task_managers:
        _task_managers[task_id] = TaskManager(task_id)
    return _task_managers[task_id]