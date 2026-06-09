"""简历评分服务：JD + 简历 + 评分规则 → 分维度得分。"""
from __future__ import annotations

from typing import Any, Dict, List

from sqlmodel import select

from app.database import session_scope
from app.llm_client import get_llm
from app.models import ScoringRule
from app.prompts import load_prompt
from app.schemas import DimensionScore
from app.utils.json_parser import parse_json
from app.utils.scoring import clamp_dimension_scores

# 岗位类别关键词（全部小写）：用于「模糊匹配」评分规则，避免岗位名一字不差。
# 顺序 = 优先级，越靠前越具体。命中后在已有规则里找标题含该词、且**最贴近**的一套。
ROLE_KEYWORDS = [
    # 安全
    "渗透测试", "ai安全", "安全开发", "安全运营", "安全研究", "网络安全",
    # AI / 数据
    "mlops", "大模型", "ai全栈", "全栈", "计算机视觉", "nlp",
    "数据科学", "数据分析", "算法工程师", "数据工程",
    # 解决方案 / 工作流
    "fde", "解决方案架构", "解决方案", "工作流",
    # 产品 / 项目（医疗在前；ai项目经理 在 项目经理 之前）
    "医疗", "ai产品经理", "产品经理", "ai项目经理", "项目经理",
    # 通用研发 / 职能
    "后端", "前端", "测试工程师", "运维", "运营", "设计师",
    # 兜底（最宽，放最后）
    "安全",
]


def resolve_ruleset_title(job_title: str) -> str:
    """把任意 JD 岗位名解析到一套已存在的评分规则岗位名。

    1) 精确命中 → 用它；
    2) 否则按「岗位类别关键词」（大小写无关）模糊匹配，命中多套时取**标题最短**
       （最贴近、最不啰嗦）的一套；
    3) 都不中 → 回退『通用』。
    """
    job_title = (job_title or "").strip()
    with session_scope() as session:
        all_titles = list(session.exec(
            select(ScoringRule.job_title).distinct()).all())
    if job_title in all_titles:
        return job_title
    jl = job_title.lower()
    custom = [t for t in all_titles if t and t != "通用"]
    for kw in ROLE_KEYWORDS:
        if kw in jl:
            cands = [t for t in custom if kw in t.lower()]
            if cands:
                return min(cands, key=len)
    return "通用"


def get_scoring_dimensions(job_title: str = "通用") -> List[Dict[str, Any]]:
    """读取评分规则维度（精确→按岗位类别模糊匹配→回退通用）。"""
    resolved = resolve_ruleset_title(job_title)
    with session_scope() as session:
        rules = session.exec(
            select(ScoringRule).where(ScoringRule.job_title == resolved)
        ).all()
        return [
            {"dimension": r.dimension, "max_score": r.max_score,
             "sub_dimension": r.sub_dimension, "description": r.description}
            for r in rules
        ]


def score_resume(jd: Dict[str, Any], resume: Dict[str, Any],
                 job_title: str = "通用") -> List[Dict[str, Any]]:
    """对简历逐维度打分，返回 DimensionScore 列表（dict）。"""
    from app.utils.formatting import format_jd, format_resume

    dimensions = get_scoring_dimensions(job_title)
    dim_text = "\n".join(
        f"- {d['dimension']}（满分 {d['max_score']}）：{d.get('description', '')}"
        for d in dimensions)
    system = load_prompt("resume_score_prompt")
    user = (
        f"【JD】\n{format_jd(jd)}\n\n【候选人简历】\n{format_resume(resume)}\n\n"
        f"【评分维度（共 {len(dimensions)} 项，请逐项打分）】\n{dim_text}\n\n"
        "请逐维度打分并给出证据与风险。"
    )

    raw = get_llm().run(
        "resume_score", system, user,
        payload={"jd": jd, "resume": resume, "dimensions": dimensions},
    )
    data = parse_json(raw, default=[])

    results: List[Dict[str, Any]] = []
    if isinstance(data, list):
        for item in data:
            try:
                results.append(DimensionScore(**item).model_dump())
            except Exception:
                continue

    # 兜底：若模型没按维度返回，则为每个维度补一个「需人工复核」记录
    if not results:
        for d in dimensions:
            results.append(DimensionScore(
                dimension=d["dimension"], score=round(d["max_score"] * 0.5, 1),
                max_score=d["max_score"], evidence=["（自动评分失败）"],
                risk=["需人工复核"], reason="模型未返回有效评分，给中性分。",
            ).model_dump())

    return clamp_dimension_scores(results)
