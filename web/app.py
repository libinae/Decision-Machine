"""FastAPI 应用入口"""

import os
import sys
from pathlib import Path

# 加载 .env 文件
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

# 添加 src 到路径
project_root = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from web.api.routes import websocket_debate

app = FastAPI(
    title="多人格决策机",
    description="基于多智能体辩论的决策辅助工具",
    version="2.0.0",
)

# 静态文件目录
static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def index():
    """主页"""
    return FileResponse(str(static_dir / "index.html"))


@app.websocket("/ws/debate")
async def ws_debate(websocket: WebSocket):
    """WebSocket 辩论入口"""
    await websocket_debate(websocket)


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)