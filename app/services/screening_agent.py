"""筛选智能体：编排「评分 → 结论 → 写库」全流程，并支持候选人排序。

设计沿用参考案例的「任务拆分」思想：抽取、评分、结论各自独立，
每一步可单测、可替换、可追溯。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlmodel import select

from app.database import session_scope
from app.llm_client import get_llm
from app.models import Application, Job, Resume, ScreeningRecord
from app.prompts import load_prompt
from app.schemas import ScreeningResult
from app.services.resume_scorer import score_resume
from app.utils.json_parser import parse_json
from app.utils.scoring import level_of, total_of


def _decide(jd: Dict[str, Any], resume: Dict[str, Any],
            dim_scores: List[Dict[str, Any]]) -> Dict[str, Any]:
    """汇总维度分 → 总分、等级、优势、风险、建议问题。"""
    system = load_prompt("screening_decision_prompt")
    user = (
        f"【JD】\n{jd}\n\n【简历】\n{resume}\n\n【维度评分】\n{dim_scores}\n\n"
        "请汇总输出筛选结论 JSON。"
    )
    raw = get_llm().run(
        "screening_decision", system, user,
        payload={"jd": jd, "resume": resume, "dimension_scores": dim_scores},
    )
    data = parse_json(raw, default={})
    try:
        result = ScreeningResult(**data) if isinstance(data, dict) else ScreeningResult()
    except Exception:
        result = ScreeningResult()

    # 总分与等级以本地计算为准，保证与维度分一致、可追溯
    computed_total = total_of(dim_scores)
    result.total_score = computed_total
    result.level = level_of(computed_total)
    result.dimension_scores = [_d(d) for d in dim_scores]
    if "仅供" not in result.summary:
        result.summary = (result.summary + " 仅供 HR 辅助参考，最终由人工确认。").strip()
    return result.model_dump()


def _d(d: Dict[str, Any]):
    from app.schemas import DimensionScore
    try:
        return DimensionScore(**d)
    except Exception:
        return DimensionScore(dimension=str(d.get("dimension", "")))


def screen(job_id: int, resume_id: int) -> Dict[str, Any]:
    """对单个 (job, resume) 执行评分 + 结论，写入 applications / screening_records。"""
    with session_scope() as session:
        job = session.get(Job, job_id)
        resume = session.get(Resume, resume_id)
        if job is None or resume is None:
            raise ValueError("job 或 resume 不存在")
        jd_dict = _job_to_dict(job)
        resume_dict = resume.structured_json or {"raw_text": resume.raw_text}
        job_title = job.job_title or "通用"

    # 评分（独立事务外执行，避免长事务）
    dim_scores = score_resume(jd_dict, resume_dict, job_title)
    decision = _decide(jd_dict, resume_dict, dim_scores)

    with session_scope() as session:
        app_row = Application(
            job_id=job_id, resume_id=resume_id,
            total_score=decision["total_score"], level=decision["level"],
            summary=decision["summary"], strengths=decision["strengths"],
            risks=decision["risks"], missing_requirements=decision["missing_requirements"],
            suggested_questions=decision["suggested_interview_questions"],
            manual_review_needed=decision["manual_review_needed"], status="screened",
        )
        session.add(app_row)
        session.flush()  # 取得 app_row.id
        for d in dim_scores:
            session.add(ScreeningRecord(
                application_id=app_row.id, dimension=d["dimension"],
                score=d["score"], max_score=d["max_score"],
                evidence=d.get("evidence", []), risk=d.get("risk", []),
                reason=d.get("reason", ""),
            ))
        application_id = app_row.id

    decision["application_id"] = application_id
    decision["job_id"] = job_id
    decision["resume_id"] = resume_id
    return decision


def process_one_resume(job_id: int, raw_text: str, file_name: str) -> Dict[str, Any]:
    """单份简历完整流水线：抽取 → 入库 → 评分结论。供并发批处理调用。"""
    from app.models import Resume
    from app.services.resume_extractor import extract_resume

    structured = extract_resume(raw_text)
    with session_scope() as session:
        resume = Resume(candidate_name=structured.get("name", ""), raw_text=raw_text,
                        structured_json=structured, file_name=file_name)
        session.add(resume)
        session.flush()
        resume_id = resume.id
    result = screen(job_id, resume_id)
    result["name"] = structured.get("name", "")
    result["file_name"] = file_name
    return result


def screen_resumes_concurrently(job_id: int, items: List[Dict[str, str]],
                                max_workers: int = 5) -> List[Dict[str, Any]]:
    """并发处理多份简历。

    items: [{"raw_text": ..., "file_name": ...}, ...]
    每份简历的「抽取+评分+结论」（3 次大模型调用，均为网络 I/O）放进独立线程，
    多份同时进行，把串行的总耗时压缩到接近单份耗时。
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if not items:
        return []
    results: List[Dict[str, Any]] = []
    workers = max(1, min(max_workers, len(items)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(process_one_resume, job_id, it["raw_text"],
                        it.get("file_name", "resume.txt")): it
            for it in items
        }
        for fut in as_completed(futures):
            it = futures[fut]
            try:
                results.append(fut.result())
            except Exception as exc:  # 单份失败不影响其他份
                results.append({"error": str(exc),
                                "file_name": it.get("file_name", "")})
    return results


def rank_for_job(job_id: int) -> List[Dict[str, Any]]:
    """按总分对某岗位的候选人排序，输出排序表。"""
    rows: List[Dict[str, Any]] = []
    with session_scope() as session:
        apps = session.exec(
            select(Application).where(Application.job_id == job_id)
            .order_by(Application.total_score.desc())
        ).all()
        for rank, app in enumerate(apps, start=1):
            resume = session.get(Resume, app.resume_id)
            s = (resume.structured_json or {}) if resume else {}
            rows.append({
                "rank": rank,
                "application_id": app.id,
                "name": s.get("name") or (resume.candidate_name if resume else ""),
                "total_score": app.total_score,
                "level": app.level,
                "highest_education": s.get("highest_education", "无"),
                "years_of_experience": s.get("years_of_experience", "无"),
                "core_skills": "、".join((s.get("skills") or [])[:5]),
                "main_strength": (app.strengths or [""])[0] if app.strengths else "",
                "main_risk": (app.risks or [""])[0] if app.risks else "",
                "next_action": _next_action(app.level),
            })
    return rows


def _next_action(level: str) -> str:
    return {
        "强烈推荐面试": "优先安排面试",
        "建议面试": "安排面试",
        "备选": "进入人才库，视情况复核",
        "暂不推荐": "暂不推进（可人工复核）",
    }.get(level, "人工复核")


def _job_to_dict(job: Job) -> Dict[str, Any]:
    return {
        "job_title": job.job_title, "department": job.department,
        "must_have_requirements": job.must_have_requirements,
        "nice_to_have_requirements": job.nice_to_have_requirements,
        "responsibilities": job.responsibilities,
        "hard_skills": job.hard_skills, "soft_skills": job.soft_skills,
        "keywords": job.keywords, "experience_requirements": job.experience_requirements,
        "education_requirements": job.education_requirements,
        "interview_focus": job.interview_focus,
    }


def get_application_detail(application_id: int) -> Optional[Dict[str, Any]]:
    """读取单个筛选结论 + 维度明细，供报告生成使用。"""
    with session_scope() as session:
        app = session.get(Application, application_id)
        if app is None:
            return None
        resume = session.get(Resume, app.resume_id)
        job = session.get(Job, app.job_id)
        records = session.exec(
            select(ScreeningRecord).where(ScreeningRecord.application_id == application_id)
        ).all()
        return {
            "application": app.model_dump(),
            "resume": (resume.structured_json if resume else {}) or {},
            "job": _job_to_dict(job) if job else {},
            "dimension_scores": [r.model_dump() for r in records],
        }
