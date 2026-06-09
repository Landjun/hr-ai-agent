"""报告生成：候选人初筛 Markdown 报告、候选人排序 Excel/Markdown/JSON 导出。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from app.config import settings
from app.services.screening_agent import get_application_detail, rank_for_job


def build_screening_markdown(application_id: int) -> str:
    """生成单个候选人的初筛 Markdown 报告。"""
    detail = get_application_detail(application_id)
    if detail is None:
        return f"# 未找到 application_id={application_id} 的筛选记录"

    app = detail["application"]
    resume = detail["resume"]
    job = detail["job"]
    dims: List[Dict[str, Any]] = detail["dimension_scores"]

    def bullets(items: List[str]) -> str:
        items = [str(i) for i in (items or []) if str(i).strip()]
        return "\n".join(f"- {i}" for i in items) or "- 无"

    lines = [
        "# 候选人初筛报告",
        "",
        "## 1. 基本信息",
        f"- 姓名：{resume.get('name', '无')}",
        f"- 最高学历：{resume.get('highest_education', '无')}　毕业院校：{resume.get('school', '无')}",
        f"- 工作年限：{resume.get('years_of_experience', '无')}",
        f"- 核心技能：{'、'.join((resume.get('skills') or [])[:8]) or '无'}",
        f"- 联系方式：{resume.get('phone', '无')} / {resume.get('email', '无')}",
        "",
        "## 2. JD 匹配结论",
        f"- 应聘岗位：{job.get('job_title', '无')}",
        f"- 一句话结论：{app.get('summary', '')}",
        "",
        "## 3. 总分与等级",
        f"- **总分：{app.get('total_score', 0)} / 100**",
        f"- **推荐等级：{app.get('level', '')}**",
        "",
        "## 4. 分维度评分",
        "",
        "| 维度 | 得分 | 满分 | 评分理由 |",
        "| --- | --- | --- | --- |",
    ]
    for d in dims:
        lines.append(
            f"| {d.get('dimension', '')} | {d.get('score', 0)} | "
            f"{d.get('max_score', 0)} | {str(d.get('reason', '')).replace(chr(10), ' ')} |"
        )

    lines += ["", "## 5. 简历证据"]
    for d in dims:
        ev = d.get("evidence") or []
        if ev:
            lines.append(f"**{d.get('dimension', '')}**")
            lines += [f"- {e}" for e in ev]
    lines += ["", "## 6. 风险点", bullets(app.get("risks", [])),
              "", "**缺口/未满足项：**", bullets(app.get("missing_requirements", [])),
              "", "## 7. 建议面试问题", bullets(app.get("suggested_questions", [])),
              "", "## 8. HR 人工复核点",
              "- 简历中『看起来强但证据不足』之处需面试核实",
              f"- 是否需要人工复核：{'是' if app.get('manual_review_needed') else '否'}",
              "- AI 不做最终录用决定，所有评分仅供辅助参考",
              "", "## 9. 最终建议",
              f"- {app.get('level', '')}：{_advice(app.get('level', ''))}",
              "", "---", "*本报告由 HR 提效智能体自动生成，仅供 HR 辅助参考，最终由人工确认。*"]
    return "\n".join(lines)


def _advice(level: str) -> str:
    return {
        "强烈推荐面试": "建议优先安排面试，重点验证高分项是否名副其实。",
        "建议面试": "建议安排面试，核实风险点。",
        "备选": "可进入人才库，结合岗位紧迫度决定是否推进。",
        "暂不推荐": "与当前岗位匹配度较低，建议人工复核后再决定。",
    }.get(level, "请人工复核。")


def save_screening_report(application_id: int) -> Path:
    """把单个候选人 Markdown 报告写入 outputs/screening_reports。"""
    md = build_screening_markdown(application_id)
    detail = get_application_detail(application_id)
    name = (detail or {}).get("resume", {}).get("name", "candidate") if detail else "candidate"
    safe = "".join(c for c in str(name) if c.isalnum() or c in "_-") or "candidate"
    path = settings.screening_report_dir / f"screening_{application_id}_{safe}.md"
    path.write_text(md, encoding="utf-8")
    return path


def export_ranking(job_id: int, fmt: str = "markdown") -> Path:
    """导出某岗位候选人排序表：markdown / excel / json。"""
    rows = rank_for_job(job_id)
    out_dir = settings.screening_report_dir

    if fmt == "json":
        path = out_dir / f"ranking_job{job_id}.json"
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    if fmt == "excel":
        import pandas as pd

        path = out_dir / f"ranking_job{job_id}.xlsx"
        pd.DataFrame(rows).to_excel(path, index=False)
        return path

    # markdown
    path = out_dir / f"ranking_job{job_id}.md"
    path.write_text(build_ranking_markdown(job_id), encoding="utf-8")
    return path


def build_ranking_markdown(job_id: int) -> str:
    """构造候选人排序表 Markdown（供导出 / 打包复用）。"""
    rows = rank_for_job(job_id)
    header = ["排名", "姓名", "总分", "推荐等级", "最高学历", "工作年限",
              "核心技能", "主要优势", "主要风险", "建议下一步"]
    keys = ["rank", "name", "total_score", "level", "highest_education",
            "years_of_experience", "core_skills", "main_strength", "main_risk", "next_action"]
    lines = ["# 候选人排序表", "", "| " + " | ".join(header) + " |",
             "| " + " | ".join(["---"] * len(header)) + " |"]
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(k, "")).replace("\n", " ") for k in keys) + " |")
    lines += ["", "*仅供 HR 辅助参考，最终由人工确认。*"]
    return "\n".join(lines)


def export_job_package(job_id: int, fmt: str = "pdf") -> bytes:
    """一键打包：把某岗位的排序表 + 全部候选人初筛报告打成一个 ZIP（字节）。

    fmt = pdf / html / markdown，决定包内报告文件格式。
    """
    import io
    import zipfile

    from app.services.report_exporter import (
        markdown_to_docx_bytes,
        markdown_to_html,
        markdown_to_pdf_bytes,
        title_from_markdown,
    )

    fmt = (fmt or "pdf").lower()
    ext = {"pdf": "pdf", "html": "html", "markdown": "md", "md": "md",
           "docx": "docx", "word": "docx"}.get(fmt, "pdf")

    def render(md: str) -> bytes:
        if ext == "md":
            return md.encode("utf-8")
        if ext == "html":
            return markdown_to_html(md, title_from_markdown(md)).encode("utf-8")
        if ext == "docx":
            return markdown_to_docx_bytes(md, title_from_markdown(md))
        return markdown_to_pdf_bytes(md, title_from_markdown(md))

    rows = rank_for_job(job_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"候选人排序表.{ext}", render(build_ranking_markdown(job_id)))
        for r in rows:
            md = build_screening_markdown(int(r["application_id"]))
            safe = "".join(c for c in str(r.get("name", "")) if c.isalnum() or c in "_-") or "候选人"
            z.writestr(f"reports/{int(r['rank']):02d}_{safe}.{ext}", render(md))
    return buf.getvalue()


def ranking_dataframe(job_id: int):
    """供 Streamlit 直接展示的 DataFrame。"""
    import pandas as pd

    return pd.DataFrame(rank_for_job(job_id))
