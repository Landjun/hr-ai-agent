"""简历相关接口：上传文件 / 粘贴文本 → 解析 + 抽取 + 存库。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session, select

from app.database import get_session
from app.models import Resume
from app.schemas import ResumeTextRequest
from app.services.resume_extractor import extract_resume
from app.services.resume_parser import parse_resume_bytes, parse_resume_text

router = APIRouter(prefix="/resumes", tags=["resumes"])


def _persist(raw_text: str, file_name: str, session: Session) -> dict:
    structured = extract_resume(raw_text)
    resume = Resume(
        candidate_name=structured.get("name", ""),
        raw_text=raw_text, structured_json=structured, file_name=file_name,
    )
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return {"resume_id": resume.id, "structured": structured}


@router.post("/upload")
async def upload_resume(file: UploadFile = File(...), session: Session = Depends(get_session)):
    data = await file.read()
    raw_text = parse_resume_bytes(data, file.filename or "resume.txt")
    return _persist(raw_text, file.filename or "resume.txt", session)


@router.post("/text")
def create_resume_from_text(req: ResumeTextRequest, session: Session = Depends(get_session)):
    raw_text = parse_resume_text(req.text)
    return _persist(raw_text, req.file_name, session)


@router.get("")
def list_resumes(session: Session = Depends(get_session)):
    rows = session.exec(select(Resume).order_by(Resume.id.desc())).all()
    return [{"id": r.id, "candidate_name": r.candidate_name,
             "file_name": r.file_name, "created_at": r.created_at} for r in rows]


@router.get("/{resume_id}")
def get_resume(resume_id: int, session: Session = Depends(get_session)):
    r = session.get(Resume, resume_id)
    if r is None:
        raise HTTPException(404, "resume 不存在")
    return r.model_dump()
