"""面试官提纲生成（第二版·模式 A：协助面试官）。

复用第一版的 JD、简历与评分报告，产出结构化面试提纲并落库。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.database import session_scope
from app.llm_client import get_llm
from app.models import Application, InterviewSession, Job, Resume
from app.prompts import load_prompt
from app.schemas import InterviewPlan
from app.services.screening_agent import _job_to_dict
from app.utils.json_parser import parse_json


def generate_plan(job_id: int, resume_id: Optional[int] = None,
                  application_id: Optional[int] = None,
                  interview_round: str = "初面",
                  duration_minutes: int = 30) -> Dict[str, Any]:
    """生成面试提纲并写入 interview_sessions(mode='assist')。"""
    with session_scope() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise ValueError("job 不存在")
        jd = _job_to_dict(job)
        resume = session.get(Resume, resume_id) if resume_id else None
        resume_dict = (resume.structured_json if resume else {}) or {}
        app = session.get(Application, application_id) if application_id else None
        score_report = app.model_dump() if app else {}

    system = load_prompt("interview_plan_prompt")
    user = (
        f"【JD】\n{jd}\n\n【简历】\n{resume_dict}\n\n【评分报告】\n{score_report}\n\n"
        f"【面试轮次】{interview_round}　【时长】{duration_minutes} 分钟\n\n请生成面试提纲 JSON。"
    )
    raw = get_llm().run(
        "interview_plan", system, user,
        payload={"jd": jd, "resume": resume_dict, "score_report": score_report,
                 "interview_round": interview_round, "duration_minutes": duration_minutes},
    )
    data = parse_json(raw, default={})
    try:
        plan = InterviewPlan(**data) if isinstance(data, dict) else InterviewPlan()
    except Exception:
        plan = InterviewPlan(interview_goal="（生成失败，请人工补充）")
    plan_dict = plan.model_dump()

    with session_scope() as session:
        sess = InterviewSession(
            job_id=job_id, resume_id=resume_id, application_id=application_id,
            mode="assist", interview_round=interview_round,
            duration_minutes=duration_minutes, status="finished",
            plan_json=plan_dict,
        )
        session.add(sess)
        session.flush()
        plan_dict["session_id"] = sess.id
    return plan_dict
