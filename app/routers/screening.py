"""简历评分 / 筛选 / 排序接口。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas import ScoreRequest
from app.services.screening_agent import get_application_detail, rank_for_job, screen

router = APIRouter(prefix="/screening", tags=["screening"])


@router.post("/score")
def score(req: ScoreRequest):
    """对 (job, resume) 评分并生成筛选结论。"""
    try:
        return screen(req.job_id, req.resume_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/ranking/{job_id}")
def ranking(job_id: int):
    return rank_for_job(job_id)


@router.get("/application/{application_id}")
def application_detail(application_id: int):
    detail = get_application_detail(application_id)
    if detail is None:
        raise HTTPException(404, "application 不存在")
    return detail
