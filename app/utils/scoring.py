"""评分换算与分级工具。

实现参考案例的「加权指标匹配」思想：
    小类得分 = (命中指标权重之和 / 该小类最高权重) × 小类满分
并提供总分分级。
"""
from __future__ import annotations

from typing import List


def weighted_subscore(matched_weight: float, max_weight: float, sub_full_score: float) -> float:
    """参考案例的小类得分公式。max_weight 为 0 时返回 0，避免除零。"""
    if max_weight <= 0:
        return 0.0
    ratio = max(0.0, min(1.0, matched_weight / max_weight))
    return round(ratio * sub_full_score, 2)


def level_of(total_score: float) -> str:
    """总分 → 推荐等级。"""
    if total_score >= 85:
        return "强烈推荐面试"
    if total_score >= 70:
        return "建议面试"
    if total_score >= 60:
        return "备选"
    return "暂不推荐"


def clamp_dimension_scores(dim_scores: List[dict]) -> List[dict]:
    """确保每个维度得分不超过其满分、不为负。"""
    for d in dim_scores:
        maxs = float(d.get("max_score", 0) or 0)
        s = float(d.get("score", 0) or 0)
        d["score"] = round(max(0.0, min(maxs, s)), 1)
    return dim_scores


def total_of(dim_scores: List[dict]) -> float:
    return round(sum(float(d.get("score", 0) or 0) for d in dim_scores), 1)
