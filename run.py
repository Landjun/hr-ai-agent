"""一键启动后端 API。

    python run.py            # 启动 FastAPI（默认 8000 端口）
    python run.py --port 9000

前端演示页面另起一个终端运行：
    streamlit run web/streamlit_app.py
"""
from __future__ import annotations

import argparse

import uvicorn

from app.config import settings
from app.database import init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="HR 提效智能体 后端")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    init_db()
    mode = "离线 Mock（未配置 API Key）" if settings.offline_mode else "真实大模型"
    print("=" * 56)
    print("  HR 提效智能体 后端启动中……")
    print(f"  当前大模型模式：{mode}")
    print(f"  API 文档：http://{args.host}:{args.port}/docs")
    print("  前端演示：streamlit run web/streamlit_app.py")
    print("=" * 56)

    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
