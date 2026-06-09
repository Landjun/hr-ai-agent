"""数据管理：清理测试 / 历史数据（评分规则始终保留）。"""
from __future__ import annotations

from sqlmodel import delete, select

from app.database import session_scope
from app.models import Application, InterviewMessage, InterviewSession, Job, Resume, ScreeningRecord


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
