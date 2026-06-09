"""面试接口：协助面试官提纲（模式 A）+ AI 模拟面试（模式 B）。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas import MockAnswerRequest, MockStartRequest, PlanRequest
from app.services.interview_agent import ask_next, finish_mock, start_mock, submit_answer
from app.services.interview_planner import generate_plan

router = APIRouter(prefix="/interviews", tags=["interviews"])


# ---- 模式 A：协助面试官 ----
@router.post("/plan")
def create_plan(req: PlanRequest):
    try:
        return generate_plan(req.job_id, req.resume_id, req.application_id,
                             req.interview_round, req.duration_minutes)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---- 模式 B：AI 模拟面试 ----
@router.post("/mock/start")
def mock_start(req: MockStartRequest):
    try:
        return start_mock(req.jd_text, req.job_id, req.resume_text,
                         req.interview_round, req.duration_minutes)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/mock/next")
def mock_next(session_id: int):
    return ask_next(session_id)


@router.post("/mock/answer")
def mock_answer(req: MockAnswerRequest):
    try:
        return submit_answer(req.session_id, req.answer)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/mock/finish")
def mock_finish(session_id: int):
    return finish_mock(session_id)
