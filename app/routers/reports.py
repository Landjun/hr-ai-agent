"""报告导出接口。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from app.database import session_scope
from app.models import InterviewSession
from app.services.report_generator import (build_screening_markdown,
                                           export_ranking, save_screening_report)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/screening/{application_id}", response_class=PlainTextResponse)
def screening_report(application_id: int, save: bool = False):
    md = build_screening_markdown(application_id)
    if save:
        save_screening_report(application_id)
    return md


@router.get("/ranking/{job_id}")
def ranking_export(job_id: int, fmt: str = "markdown"):
    """导出排序表，fmt = markdown / excel / json。"""
    path = export_ranking(job_id, fmt)
    return FileResponse(str(path), filename=path.name)


@router.get("/interview/{session_id}", response_class=PlainTextResponse)
def interview_report(session_id: int):
    with session_scope() as session:
        sess = session.get(InterviewSession, session_id)
        if sess is None:
            raise HTTPException(404, "session 不存在")
        return sess.final_report or "（该面试尚未结束或未生成报告）"
