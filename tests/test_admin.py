"""数据管理（删除 / 清空）离线测试。"""
from sqlmodel import func, select

from app.database import session_scope
from app.models import Application, Job, Resume, ScreeningRecord, ScoringRule
from app.services.admin import delete_job, reset_all_data
from app.services.screening_agent import screen


def _seed_one():
    with session_scope() as s:
        job = Job(job_title="通用", jd_text="x", hard_skills=["python"], keywords=["python"])
        r = Resume(candidate_name="甲", raw_text="熟悉 Python",
                   structured_json={"name": "甲", "skills": ["python"], "raw_text": "熟悉 Python"})
        s.add(job); s.add(r); s.flush()
        jid, rid = job.id, r.id
    screen(jid, rid)
    return jid


def _count(model):
    with session_scope() as s:
        return s.exec(select(func.count()).select_from(model)).one()


def test_delete_job_removes_related_rows():
    jid = _seed_one()
    assert _count(Application) >= 1
    delete_job(jid)
    with session_scope() as s:
        assert s.get(Job, jid) is None
        assert s.exec(select(Application).where(Application.job_id == jid)).first() is None


def test_reset_keeps_rules_clears_data():
    _seed_one()
    rules_before = _count(ScoringRule)
    assert rules_before > 0
    reset_all_data()
    assert _count(Job) == 0
    assert _count(Resume) == 0
    assert _count(Application) == 0
    assert _count(ScreeningRecord) == 0
    assert _count(ScoringRule) == rules_before  # 规则保留
