"""数据管理：清理测试 / 历史数据 + 评分规则管理。"""
from __future__ import annotations

from typing import Dict, List

from sqlmodel import delete, select

from app.database import session_scope
from app.models import (
    Application,
    InterviewMessage,
    InterviewSession,
    Job,
    Resume,
    ScoringRule,
    ScreeningRecord,
)


def reset_all_data() -> None:
    """清空岗位 / 简历 / 投递 / 评分明细 / 面试数据（保留评分规则）。不可恢复。"""
    with session_scope() as s:
        for model in (InterviewMessage, InterviewSession, ScreeningRecord,
                      Application, Resume, Job):
            s.exec(delete(model))


def delete_job(job_id: int) -> None:
    """删除某岗位及其全部投递、评分明细与面试会话（消息一并删）。"""
    with session_scope() as s:
        app_ids = [a.id for a in s.exec(
            select(Application).where(Application.job_id == job_id)).all()]
        if app_ids:
            s.exec(delete(ScreeningRecord).where(
                ScreeningRecord.application_id.in_(app_ids)))
            s.exec(delete(Application).where(Application.id.in_(app_ids)))
        sess_ids = [x.id for x in s.exec(
            select(InterviewSession).where(InterviewSession.job_id == job_id)).all()]
        if sess_ids:
            s.exec(delete(InterviewMessage).where(
                InterviewMessage.session_id.in_(sess_ids)))
            s.exec(delete(InterviewSession).where(InterviewSession.id.in_(sess_ids)))
        s.exec(delete(Job).where(Job.id == job_id))


def delete_application(application_id: int) -> None:
    """删除单条筛选记录及其维度明细。"""
    with session_scope() as s:
        s.exec(delete(ScreeningRecord).where(
            ScreeningRecord.application_id == application_id))
        s.exec(delete(Application).where(Application.id == application_id))


# --------------------------- 评分规则管理 ---------------------------
def list_ruleset_titles() -> List[str]:
    """所有评分规则岗位名（通用排在最前）。"""
    with session_scope() as s:
        titles = list(s.exec(select(ScoringRule.job_title).distinct()).all())
    titles = sorted(set(titles), key=lambda t: (t != "通用", t))
    return titles


def get_ruleset(job_title: str) -> List[Dict]:
    """读取某岗位的评分规则维度明细。"""
    with session_scope() as s:
        rows = s.exec(
            select(ScoringRule).where(ScoringRule.job_title == job_title)
            .order_by(ScoringRule.id)
        ).all()
        return [{"id": r.id, "dimension": r.dimension, "max_score": r.max_score,
                 "description": r.description} for r in rows]


def update_ruleset_scores(job_title: str, scores: Dict[str, float]) -> float:
    """按维度名更新某岗位规则的满分，返回更新后的总分。"""
    total = 0.0
    with session_scope() as s:
        rows = s.exec(
            select(ScoringRule).where(ScoringRule.job_title == job_title)).all()
        for r in rows:
            if r.dimension in scores:
                r.max_score = float(max(0.0, scores[r.dimension]))
                s.add(r)
            total += r.max_score
    return round(total, 1)
