"""FastAPI 应用入口。

启动时自动建表 + 写入默认评分规则。包含 Dashboard 统计接口。
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import func, select

from app.config import settings
from app.database import engine, init_db
from app.llm_client import get_llm
from app.models import Application, InterviewSession, Job, Resume
from app.routers import interviews, jobs, reports, resumes, screening


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="HR 提效智能体 API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(resumes.router)
app.include_router(screening.router)
app.include_router(interviews.router)
app.include_router(reports.router)


@app.get("/")
def root():
    return {"name": "HR 提效智能体", "version": "0.1.0",
            "llm_mode": get_llm().mode, "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok", "offline_mode": settings.offline_mode}


@app.get("/stats")
def stats():
    """首页 Dashboard 数据。"""
    from sqlmodel import Session

    with Session(engine) as session:
        def count(model):
            return session.exec(select(func.count()).select_from(model)).one()

        return {
            "jobs": count(Job),
            "resumes": count(Resume),
            "screenings": count(Application),
            "interviews": count(InterviewSession),
            "llm_mode": get_llm().mode,
        }
