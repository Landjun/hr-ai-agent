"""报告导出接口。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, Response

from app.database import session_scope
from app.models import InterviewSession
from app.services.report_exporter import (markdown_to_html, markdown_to_pdf_bytes,
                                          title_from_markdown)
from app.services.report_generator import (build_screening_markdown,
                                           export_job_package, export_ranking,
                                           save_screening_report)

router = APIRouter(prefix="/reports", tags=["reports"])


def _render(md: str, fmt: str, filename: str):
    """按 fmt 返回 markdown / html / pdf 响应。"""
    fmt = (fmt or "markdown").lower()
    if fmt in ("md", "markdown"):
        return PlainTextResponse(md)
    title = title_from_markdown(md)
    if fmt == "html":
        return Response(markdown_to_html(md, title), media_type="text/html")
    if fmt == "pdf":
        return Response(
            markdown_to_pdf_bytes(md, title), media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'})
    raise HTTPException(400, "fmt 仅支持 markdown / html / pdf")


@router.get("/screening/{application_id}")
def screening_report(application_id: int, fmt: str = "markdown", save: bool = False):
    """初筛报告，fmt = markdown / html / pdf。"""
    md = build_screening_markdown(application_id)
    if save:
        save_screening_report(application_id)
    return _render(md, fmt, f"screening_{application_id}")


@router.get("/ranking/{job_id}")
def ranking_export(job_id: int, fmt: str = "markdown"):
    """导出排序表，fmt = markdown / excel / json。"""
    path = export_ranking(job_id, fmt)
    return FileResponse(str(path), filename=path.name)


@router.get("/package/{job_id}")
def package_export(job_id: int, fmt: str = "pdf"):
    """一键打包：排序表 + 全部候选人初筛报告 → ZIP（fmt = pdf / html / markdown）。"""
    data = export_job_package(job_id, fmt)
    return Response(
        data, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="job_{job_id}_reports.zip"'})


@router.get("/interview/{session_id}")
def interview_report(session_id: int, fmt: str = "markdown"):
    """面试报告，fmt = markdown / html / pdf。"""
    with session_scope() as session:
        sess = session.get(InterviewSession, session_id)
        if sess is None:
            raise HTTPException(404, "session 不存在")
        md = sess.final_report or "（该面试尚未结束或未生成报告）"
    return _render(md, fmt, f"interview_{session_id}")
