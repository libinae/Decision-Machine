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
from fastapi.middleware.cors import CORSMiddleware

from web.api.routes import websocket_debate
from web.api.sse_routes import router as sse_router

app = FastAPI(
    title="多人格决策机",
    description="基于多智能体辩论的决策辅助工具",
    version="2.1.0",
)

# CORS 配置（支持函数计算部署）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件目录
static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def index():
    """主页"""
    return FileResponse(str(static_dir / "index.html"))


@app.get("/fc")
async def fc_index():
    """函数计算版主页（SSE）"""
    return FileResponse(str(static_dir / "index_fc.html"))


@app.websocket("/ws/debate")
async def ws_debate(websocket: WebSocket):
    """WebSocket 辩论入口"""
    await websocket_debate(websocket)


# 注册 SSE 路由（用于函数计算）
app.include_router(sse_router)


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "version": "2.1.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)