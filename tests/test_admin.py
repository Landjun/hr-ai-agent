"""数据管理（删除 / 清空）离线测试。"""
from sqlmodel import func, select

from app.database import session_scope
from app.models import Application, Job, Resume, ScoringRule, ScreeningRecord
from app.services.admin import delete_job, reset_all_data
from app.services.screening_agent import screen


def _seed_one():
    with session_scope() as s:
        job = Job(job_title="通用", jd_text="x", hard_skills=["python"], keywords=["python"])
        r = Resume(candidate_name="甲", raw_text="熟悉 Python",
                   structured_json={"name": "甲", "skills": ["python"], "raw_text": "熟悉 Python"})
        s.add(job)
        s.add(r)
        s.flush()
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


def test_ruleset_routing_and_edit():
    from app.services.admin import get_ruleset, list_ruleset_titles, update_ruleset_scores
    from app.services.resume_scorer import resolve_ruleset_title

    titles = list_ruleset_titles()
    assert {"通用", "医疗AI产品经理", "算法工程师", "网络安全渗透测试工程师",
            "AI安全工程师", "大模型应用开发工程师", "AI产品经理", "后端开发工程师"} <= set(titles)
    assert titles[0] == "通用"  # 通用排最前

    # 岗位类别模糊路由
    assert resolve_ruleset_title("机器学习算法工程师") == "算法工程师"
    assert resolve_ruleset_title("高级渗透测试工程师") == "网络安全渗透测试工程师"
    assert resolve_ruleset_title("大模型AI安全专家") == "AI安全工程师"  # ai安全优先于大模型
    assert resolve_ruleset_title("AI 应用工程师（大模型方向）") == "大模型应用开发工程师"
    assert resolve_ruleset_title("医疗AI产品经理") == "医疗AI产品经理"  # 医疗优先
    assert resolve_ruleset_title("AI高级产品经理") == "AI产品经理"  # 通用 AI PM
    assert resolve_ruleset_title("Java后端开发工程师") == "后端开发工程师"
    assert resolve_ruleset_title("Go 工程师") == "通用"  # 无具体匹配 → 通用
    # 新增岗位
    assert resolve_ruleset_title("资深安全开发工程师") == "安全开发工程师"
    assert resolve_ruleset_title("AI全栈开发工程师") == "AI全栈工程师"
    assert resolve_ruleset_title("FDE 解决方案架构师") == "FDE解决方案架构师"
    assert resolve_ruleset_title("资深AI项目经理") == "AI项目经理"
    assert resolve_ruleset_title("业务工作流工程师") == "工作流工程师"

    # 编辑满分立即生效
    rules = get_ruleset("算法工程师")
    d0, base = rules[0]["dimension"], rules[0]["max_score"]
    update_ruleset_scores("算法工程师", {d0: base + 5})
    after = {r["dimension"]: r["max_score"] for r in get_ruleset("算法工程师")}
    assert after[d0] == base + 5


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
