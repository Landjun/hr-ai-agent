"""JD / 岗位相关接口。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Job
from app.schemas import JDCreateRequest
from app.services.jd_parser import parse_jd

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/parse")
def parse_and_create_job(req: JDCreateRequest, session: Session = Depends(get_session)):
    """解析 JD 文本并存库，返回结构化 JD。"""
    structured = parse_jd(req.jd_text)
    job = Job(
        job_title=structured.get("job_title", ""),
        department=structured.get("department", ""),
        jd_text=req.jd_text,
        must_have_requirements=structured.get("must_have_requirements", []),
        nice_to_have_requirements=structured.get("nice_to_have_requirements", []),
        responsibilities=structured.get("responsibilities", []),
        hard_skills=structured.get("hard_skills", []),
        soft_skills=structured.get("soft_skills", []),
        keywords=structured.get("keywords", []),
        experience_requirements=structured.get("experience_requirements", ""),
        education_requirements=structured.get("education_requirements", ""),
        interview_focus=structured.get("interview_focus", []),
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return {"job_id": job.id, "structured": structured}


@router.get("")
def list_jobs(session: Session = Depends(get_session)):
    jobs = session.exec(select(Job).order_by(Job.id.desc())).all()
    return [{"id": j.id, "job_title": j.job_title, "created_at": j.created_at} for j in jobs]


@router.get("/{job_id}")
def get_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "job 不存在")
    return job.model_dump()
