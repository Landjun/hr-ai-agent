"""AI 模拟面试智能体（第二版·模式 B）。

核心交互纪律：一次只问一个问题；回答后先短评再追问/进入下一题；
结束后生成完整报告。状态保存在 interview_sessions + interview_messages。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlmodel import select

from app.database import session_scope
from app.llm_client import get_llm
from app.models import InterviewMessage, InterviewSession, Job, Resume
from app.prompts import load_prompt
from app.schemas import MockQuestion
from app.services.interview_evaluator import build_final_report, evaluate_answer
from app.services.jd_parser import parse_jd
from app.services.resume_extractor import extract_resume
from app.services.screening_agent import _job_to_dict
from app.utils.json_parser import parse_json

# 时长 → 题量
_DURATION_TO_QUESTIONS = {15: 3, 30: 4, 45: 5, 60: 6}


def start_mock(jd_text: Optional[str] = None, job_id: Optional[int] = None,
               resume_text: Optional[str] = None, interview_round: str = "技术面",
               duration_minutes: int = 30) -> Dict[str, Any]:
    """开始一场模拟面试，返回 session_id 与第一题。"""
    # 1. 解析 / 复用 JD
    with session_scope() as session:
        if job_id:
            job = session.get(Job, job_id)
            if job is None:
                raise ValueError("job 不存在")
            jd = _job_to_dict(job)
        elif jd_text and jd_text.strip():
            jd = parse_jd(jd_text)
            job = Job(job_title=jd.get("job_title", ""), jd_text=jd_text,
                      must_have_requirements=jd.get("must_have_requirements", []),
                      nice_to_have_requirements=jd.get("nice_to_have_requirements", []),
                      responsibilities=jd.get("responsibilities", []),
                      hard_skills=jd.get("hard_skills", []),
                      soft_skills=jd.get("soft_skills", []),
                      keywords=jd.get("keywords", []),
                      experience_requirements=jd.get("experience_requirements", ""),
                      education_requirements=jd.get("education_requirements", ""),
                      interview_focus=jd.get("interview_focus", []))
            session.add(job)
            session.flush()
            job_id = job.id
        else:
            raise ValueError("必须提供 jd_text 或 job_id")

        # 2. 可选简历
        resume_id = None
        resume_dict: Dict[str, Any] = {}
        if resume_text and resume_text.strip():
            resume_dict = extract_resume(resume_text)
            r = Resume(candidate_name=resume_dict.get("name", ""),
                       raw_text=resume_text, structured_json=resume_dict,
                       file_name="mock_interview.txt")
            session.add(r)
            session.flush()
            resume_id = r.id

        max_q = _DURATION_TO_QUESTIONS.get(duration_minutes, 4)
        sess = InterviewSession(
            job_id=job_id, resume_id=resume_id, mode="mock",
            interview_round=interview_round, duration_minutes=duration_minutes,
            status="active",
            plan_json={"jd": jd, "resume": resume_dict, "asked_titles": [],
                       "max_questions": max_q},
        )
        session.add(sess)
        session.flush()
        session_id = sess.id

    first_q = ask_next(session_id)
    return {"session_id": session_id, "max_questions": max_q,
            "jd": jd, "question": first_q}


def _load(session_id: int):
    with session_scope() as session:
        sess = session.get(InterviewSession, session_id)
        if sess is None:
            raise ValueError("session 不存在")
        msgs = session.exec(
            select(InterviewMessage).where(InterviewMessage.session_id == session_id)
            .order_by(InterviewMessage.id)
        ).all()
        return sess.model_dump(), [m.model_dump() for m in msgs]


def ask_next(session_id: int) -> Dict[str, Any]:
    """产出下一题（一次只问一个）。"""
    sess, msgs = _load(session_id)
    plan = sess.get("plan_json", {}) or {}
    jd = plan.get("jd", {})
    asked = plan.get("asked_titles", [])
    index = len([m for m in msgs if m["role"] == "interviewer"]) + 1

    system = load_prompt("interview_agent_prompt")
    user = f"【JD】{jd}\n已问过：{asked}\n请出第 {index} 个问题。"
    raw = get_llm().run("interview_question", system, user,
                        payload={"jd": jd, "asked_titles": asked, "index": index})
    data = parse_json(raw, default={})
    try:
        q = MockQuestion(**data) if isinstance(data, dict) else MockQuestion(index=index)
    except Exception:
        q = MockQuestion(index=index, title="综合", question="请介绍你最有代表性的一段经历。",
                         dimension="综合")
    q.index = index
    qd = q.model_dump()

    with session_scope() as session:
        session.add(InterviewMessage(
            session_id=session_id, role="interviewer", content=qd["question"],
            dimension=qd["dimension"], feedback={"title": qd["title"], "index": index},
        ))
        s = session.get(InterviewSession, session_id)
        new_plan = dict(s.plan_json or {})
        titles = list(new_plan.get("asked_titles", []))
        titles.append(qd["title"])
        new_plan["asked_titles"] = titles
        s.plan_json = new_plan
        session.add(s)
    return qd


def submit_answer(session_id: int, answer: str) -> Dict[str, Any]:
    """提交回答 → 即时点评打分；返回反馈与是否应结束。"""
    sess, msgs = _load(session_id)
    plan = sess.get("plan_json", {}) or {}
    jd = plan.get("jd", {})
    max_q = plan.get("max_questions", 4)

    # 找到最近一条面试官问题
    interviewer_msgs = [m for m in msgs if m["role"] == "interviewer"]
    if not interviewer_msgs:
        raise ValueError("尚未提问，无法作答")
    last_q = interviewer_msgs[-1]
    question = {"question": last_q["content"], "dimension": last_q.get("dimension", ""),
                "title": (last_q.get("feedback") or {}).get("title", "")}

    feedback = evaluate_answer(question, answer, jd)

    with session_scope() as session:
        session.add(InterviewMessage(
            session_id=session_id, role="candidate", content=answer,
            dimension=question["dimension"], score=feedback["score"],
            feedback={**feedback, "title": question["title"],
                      "question": question["question"]},
        ))

    answered = len([m for m in msgs if m["role"] == "candidate"]) + 1
    should_finish = answered >= max_q
    return {"feedback": feedback, "answered": answered, "max_questions": max_q,
            "should_finish": should_finish, "title": question["title"]}


def build_transcript(session_id: int) -> List[Dict[str, Any]]:
    """整理逐题问答 + 评分，供生成报告。"""
    _, msgs = _load(session_id)
    transcript: List[Dict[str, Any]] = []
    pending_q: Optional[Dict[str, Any]] = None
    for m in msgs:
        if m["role"] == "interviewer":
            pending_q = {"title": (m.get("feedback") or {}).get("title", ""),
                         "dimension": m.get("dimension", ""), "question": m["content"]}
        elif m["role"] == "candidate":
            fb = m.get("feedback") or {}
            entry = {
                "title": fb.get("title", pending_q["title"] if pending_q else ""),
                "dimension": m.get("dimension", ""),
                "question": fb.get("question", pending_q["question"] if pending_q else ""),
                "answer": m["content"], "score": m.get("score"),
                "highlights": fb.get("highlights", []), "gaps": fb.get("gaps", []),
            }
            transcript.append(entry)
            pending_q = None
    return transcript


def finish_mock(session_id: int) -> Dict[str, Any]:
    """结束面试，生成最终报告并落库。"""
    sess, _ = _load(session_id)
    plan = sess.get("plan_json", {}) or {}
    jd = plan.get("jd", {})
    resume = plan.get("resume", {})
    transcript = build_transcript(session_id)
    report = build_final_report(jd, transcript, resume)

    with session_scope() as session:
        s = session.get(InterviewSession, session_id)
        s.status = "finished"
        s.final_score = report["final_score"]
        s.final_report = report["report_markdown"]
        session.add(s)
    report["session_id"] = session_id
    report["transcript"] = transcript
    return report
