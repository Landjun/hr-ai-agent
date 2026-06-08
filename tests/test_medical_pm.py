"""医疗AI产品经理 岗位专属评分规则的离线测试。"""
from pathlib import Path

from sqlmodel import select

from app.database import session_scope
from app.models import Job, Resume, ScoringRule
from app.services.jd_parser import parse_jd
from app.services.resume_extractor import extract_resume
from app.services.resume_scorer import get_scoring_dimensions
from app.services.screening_agent import screen

DATA = Path(__file__).resolve().parent.parent / "data"


def _read(name: str) -> str:
    return (DATA / name).read_text(encoding="utf-8")


def test_medical_pm_ruleset_seeded():
    dims = get_scoring_dimensions("医疗AI产品经理")
    names = {d["dimension"] for d in dims}
    assert "医疗行业理解" in names
    assert "AI产品能力" in names
    assert "项目与商业化结果" in names
    assert round(sum(d["max_score"] for d in dims)) == 100


def test_medical_jd_title_routes_to_ruleset():
    jd = parse_jd(_read("sample_jd_medical_pm.md"))
    assert jd["job_title"] == "医疗AI产品经理"


def _make_job(jd_text):
    jd = parse_jd(jd_text)
    with session_scope() as s:
        job = Job(job_title=jd["job_title"], jd_text=jd_text,
                  must_have_requirements=jd["must_have_requirements"],
                  hard_skills=jd["hard_skills"], keywords=jd["keywords"])
        s.add(job)
        s.flush()
        return job.id


def _make_resume(text):
    st = extract_resume(text)
    with session_scope() as s:
        r = Resume(candidate_name=st.get("name", ""), raw_text=text, structured_json=st)
        s.add(r)
        s.flush()
        return r.id


def test_strong_medical_pm_beats_weak():
    job_id = _make_job(_read("sample_jd_medical_pm.md"))
    strong = screen(job_id, _make_resume(_read("sample_resume_medical_pm_strong.md")))
    weak = screen(job_id, _make_resume(_read("sample_resume_medical_pm_weak.md")))
    assert strong["total_score"] > weak["total_score"]
    assert strong["level"] == "强烈推荐面试"
    # 维度按医疗PM规则展开，且每维有证据
    dims = {d["dimension"] for d in strong["dimension_scores"]}
    assert "医疗行业理解" in dims
    for d in strong["dimension_scores"]:
        assert d["evidence"]
