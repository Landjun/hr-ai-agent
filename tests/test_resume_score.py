"""评分与筛选流程的离线测试。"""
from app.database import session_scope
from app.models import Job, Resume
from app.services.jd_parser import parse_jd
from app.services.resume_extractor import extract_resume
from app.services.resume_scorer import score_resume
from app.services.screening_agent import rank_for_job, screen
from app.utils.scoring import level_of, total_of

JD = "招聘岗位：AI 应用工程师\n要求：精通 Python，掌握 RAG、Agent、FastAPI。本科及以上 3 年经验。"
STRONG = "姓名：张伟\n硕士 北京航空航天大学 6年\n精通 Python FastAPI RAG Agent LangChain\n项目：RAG 客服系统，工单下降45%"
WEAK = "姓名：李娜\n本科 3年\n熟悉 Python Django\n了解大模型 API"


def _make_job_and_resume(jd_text, resume_text):
    jd = parse_jd(jd_text)
    resume = extract_resume(resume_text)
    with session_scope() as s:
        job = Job(job_title=jd["job_title"], jd_text=jd_text,
                  must_have_requirements=jd["must_have_requirements"],
                  hard_skills=jd["hard_skills"], keywords=jd["keywords"])
        r = Resume(candidate_name=resume["name"], raw_text=resume_text,
                   structured_json=resume)
        s.add(job)
        s.add(r)
        s.flush()
        return job.id, r.id, jd, resume


def test_score_dimensions_sum_to_total():
    _, _, jd, resume = _make_job_and_resume(JD, STRONG)
    dims = score_resume(jd, resume)
    assert len(dims) == 7
    for d in dims:
        assert 0 <= d["score"] <= d["max_score"]
        assert d["evidence"]  # 必须有证据
    assert total_of(dims) <= 100


def test_strong_beats_weak():
    jid, sid_strong, jd, _ = _make_job_and_resume(JD, STRONG)
    res_strong = screen(jid, sid_strong)

    _, sid_weak, _, _ = _make_job_and_resume(JD, WEAK)
    # 用同一个岗位评弱简历
    res_weak = screen(jid, sid_weak)

    assert res_strong["total_score"] > res_weak["total_score"]
    assert "仅供" in res_strong["summary"]  # 安全声明
    assert res_strong["manual_review_needed"] is True


def test_ranking_orders_by_score():
    jid, sid_strong, jd, _ = _make_job_and_resume(JD, STRONG)
    screen(jid, sid_strong)
    _, sid_weak, _, _ = _make_job_and_resume(JD, WEAK)
    screen(jid, sid_weak)
    ranking = rank_for_job(jid)
    assert ranking[0]["total_score"] >= ranking[-1]["total_score"]
    assert ranking[0]["rank"] == 1


def test_level_thresholds():
    assert level_of(90) == "强烈推荐面试"
    assert level_of(75) == "建议面试"
    assert level_of(65) == "备选"
    assert level_of(50) == "暂不推荐"
