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


def get_scoring_dimensions(job_title: str = "通用") -> List[Dict[str, Any]]:
    """读取评分规则维度（优先岗位专属，回退通用）。"""
    with session_scope() as session:
        rules = session.exec(
            select(ScoringRule).where(ScoringRule.job_title == job_title)
        ).all()
        if not rules:
            rules = session.exec(
                select(ScoringRule).where(ScoringRule.job_title == "通用")
            ).all()
        return [
            {"dimension": r.dimension, "max_score": r.max_score,
             "sub_dimension": r.sub_dimension, "description": r.description}
            for r in rules
        ]


def score_resume(jd: Dict[str, Any], resume: Dict[str, Any],
                 job_title: str = "通用") -> List[Dict[str, Any]]:
    """对简历逐维度打分，返回 DimensionScore 列表（dict）。"""
    dimensions = get_scoring_dimensions(job_title)
    system = load_prompt("resume_score_prompt")
    user = (
        f"【JD】\n{jd}\n\n【候选人简历】\n{resume}\n\n"
        f"【评分维度】\n{dimensions}\n\n请逐维度打分并给出证据与风险。"
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
