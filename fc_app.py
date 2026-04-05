"""阿里云函数计算入口

适配 FC HTTP 触发器
"""

import os
import sys
from pathlib import Path

# 加载环境变量
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)

# 添加路径
project_root = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from web.api.sse_routes import router as sse_router

# 创建 FastAPI 应用
app = FastAPI(
    title="多人格决策机",
    description="基于多智能体辩论的决策辅助工具 - 函数计算版",
    version="2.1.0",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 SSE 路由
app.include_router(sse_router)

# 静态文件目录
static_dir = Path(__file__).resolve().parent / "web" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def index():
    """主页"""
    fc_index = static_dir / "index_fc.html"
    if fc_index.exists():
        return FileResponse(str(fc_index))
    return FileResponse(str(static_dir / "index.html"))


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "version": "2.1.0-fc"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    return JSONResponse(
        status_code=500,
        content={"error": str(exc)},
    )


def main(event, context):
    """函数计算入口函数

    Args:
        event: FC 事件对象，包含 HTTP 请求信息
        context: FC 上下文对象

    Returns:
        HTTP 响应
    """
    # 从 event 中提取请求信息
    if isinstance(event, dict):
        # HTTP 触发器格式
        method = event.get("method", "GET")
        path = event.get("path", "/")
        headers = event.get("headers", {})
        queries = event.get("queries", {})
        body = event.get("body", "")

        # 构建 ASGI scope
        scope = {
            "type": "http",
            "method": method,
            "path": path,
            "query_string": "",
            "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
            "server": ("0.0.0.0", 8080),
            "asgi": {"version": "3.0"},
        }

        # 处理查询参数
        if queries:
            query_parts = [f"{k}={v}" for k, v in queries.items()]
            scope["query_string"] = "&".join(query_parts).encode()

        # 使用 Starlette 处理请求
        from starlette.responses import Response

        async def receive():
            return {"type": "http.request", "body": body.encode() if body else b""}

        # 这里需要更完整的 ASGI 处理
        # 实际部署时建议使用 FC 的 Web 函数模式
        return {"statusCode": 200, "body": "Use FC Web Function mode"}

    return {"statusCode": 400, "body": "Invalid event format"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)