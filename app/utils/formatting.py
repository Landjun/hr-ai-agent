"""把 JD / 简历的结构化字典，格式化成干净、可读的文本送给大模型。

相比直接 `f"{dict}"`（Python 字典原文，含大量引号/花括号/英文键名），
干净分段文本能让模型更准地理解与引用证据，且 token 更少 → 更准也更快。
"""
from __future__ import annotations

from typing import Any, Dict, List


def _bullets(items: List[Any]) -> str:
    return "\n".join(f"- {str(x).strip()}" for x in (items or []) if str(x).strip())


def format_jd(jd: Dict[str, Any]) -> str:
    """JD 字典 → 分段文本。"""
    out: List[str] = [f"岗位名称：{jd.get('job_title', '') or '未命名'}"]
    if jd.get("department"):
        out.append(f"部门：{jd['department']}")
    if jd.get("experience_requirements"):
        out.append(f"经验要求：{jd['experience_requirements']}")
    if jd.get("education_requirements"):
        out.append(f"学历要求：{jd['education_requirements']}")

    def section(title: str, items: List[Any]) -> None:
        body = _bullets(items)
        if body:
            out.append(f"\n【{title}】\n{body}")

    section("必备要求", jd.get("must_have_requirements"))
    section("加分项", jd.get("nice_to_have_requirements"))
    section("岗位职责", jd.get("responsibilities"))
    if jd.get("hard_skills"):
        out.append(f"\n硬技能要求：{'、'.join(jd['hard_skills'])}")
    if jd.get("soft_skills"):
        out.append(f"软技能要求：{'、'.join(jd['soft_skills'])}")
    return "\n".join(out)


def format_resume(resume: Dict[str, Any], raw_excerpt: int = 1500) -> str:
    """简历字典 → 分段文本（含原文节选，便于模型引用证据）。"""
    out: List[str] = [f"姓名：{resume.get('name', '') or '无'}"]
    for label, key in [("最高学历", "highest_education"), ("毕业院校", "school"),
                       ("专业", "major"), ("工作年限", "years_of_experience"),
                       ("求职意向", "expected_position"), ("期望城市", "expected_city")]:
        v = resume.get(key)
        if v and v != "无":
            out.append(f"{label}：{v}")
    if resume.get("skills"):
        out.append(f"技能：{'、'.join(resume['skills'])}")

    works = resume.get("work_experiences") or []
    if works:
        out.append("\n【工作经历】")
        for w in works:
            seg = f"- {w.get('company', '')} {w.get('position', '')} " \
                  f"{w.get('start_date', '')}~{w.get('end_date', '')}".strip()
            desc = (w.get("description") or "").strip()
            out.append(seg + (f"：{desc[:200]}" if desc else ""))

    projs = resume.get("project_experiences") or []
    if projs:
        out.append("\n【项目经历】")
        for p in projs:
            ach = "；".join(p.get("achievements") or [])
            desc = (p.get("description") or "").strip()
            line = f"- {p.get('project_name', '')}（{p.get('role', '')}）"
            if desc:
                line += f"：{desc[:250]}"
            if ach:
                line += f"　量化成果：{ach}"
            if p.get("tech_stack"):
                line += f"　技术栈：{'、'.join(p['tech_stack'])}"
            out.append(line)

    if resume.get("self_evaluation") and resume["self_evaluation"] != "无":
        out.append(f"\n自我评价：{str(resume['self_evaluation'])[:300]}")

    raw = (resume.get("raw_text") or "").strip()
    if raw:
        out.append(f"\n【简历原文（节选，供核对证据）】\n{raw[:raw_excerpt]}")
    return "\n".join(out)
