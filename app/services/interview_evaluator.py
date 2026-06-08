"""面试评估（第二版·模式 B 配套）：单轮回答打分 + 最终面试报告。"""
from __future__ import annotations

from typing import Any, Dict, List

from app.llm_client import get_llm
from app.prompts import load_prompt
from app.schemas import AnswerFeedback
from app.utils.json_parser import parse_json


def evaluate_answer(question: Dict[str, Any], answer: str,
                    jd: Dict[str, Any]) -> Dict[str, Any]:
    """对候选人单轮回答打分，返回 AnswerFeedback dict。"""
    system = load_prompt("interview_evaluate_prompt")
    user = (
        f"【问题】{question.get('question', '')}\n"
        f"【考察维度】{question.get('dimension', '')}\n"
        f"【候选人回答】{answer}\n\n【JD】{jd}\n\n请点评并打分。"
    )
    raw = get_llm().run(
        "answer_feedback", system, user,
        payload={"question": question, "answer": answer, "jd": jd},
    )
    data = parse_json(raw, default={})
    try:
        fb = AnswerFeedback(**data) if isinstance(data, dict) else AnswerFeedback()
    except Exception:
        fb = AnswerFeedback(score=5, gaps=["自动点评失败，请人工复核"])
    fb.score = round(max(0.0, min(10.0, fb.score)), 1)
    return fb.model_dump()


def build_final_report(jd: Dict[str, Any], transcript: List[Dict[str, Any]],
                       resume: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """根据逐轮问答与评分，生成 JD 模拟面试报告（Markdown）+ 总分。

    transcript: [{title, dimension, question, answer, score, highlights, gaps}]
    """
    scored = [t for t in transcript if t.get("score") is not None]
    avg10 = round(sum(t["score"] for t in scored) / len(scored), 1) if scored else 0.0
    final_100 = round(avg10 * 10, 1)

    # 维度聚合
    dim_scores: Dict[str, List[float]] = {}
    for t in scored:
        dim_scores.setdefault(t.get("dimension", "综合"), []).append(t["score"])
    dim_avg = {k: round(sum(v) / len(v), 1) for k, v in dim_scores.items()}

    all_gaps: List[str] = []
    for t in transcript:
        all_gaps += t.get("gaps", []) or []
    weak = sorted(set(all_gaps), key=lambda g: -all_gaps.count(g))[:5]

    def grade(s: float) -> str:
        if s >= 80:
            return "表现优秀"
        if s >= 65:
            return "表现良好"
        if s >= 50:
            return "基本合格，有明显短板"
        return "短板较多，需重点提升"

    lines = [
        "# JD 模拟面试报告",
        "",
        "## 1. 岗位理解",
        f"- 目标岗位：{jd.get('job_title', '无')}",
        f"- 核心要求：{'、'.join((jd.get('hard_skills') or jd.get('keywords') or [])[:6]) or '无'}",
        "",
        "## 2. 面试总体表现",
        f"- **综合得分：{final_100} / 100（{grade(final_100)}）**",
        f"- 共回答 {len(scored)} 题，平均每题 {avg10} / 10",
        "",
        "## 3. 分维度得分",
        "",
        "| 维度 | 平均分(/10) |",
        "| --- | --- |",
    ]
    for k, v in dim_avg.items():
        lines.append(f"| {k} | {v} |")

    lines += ["", "## 4. 每道题表现复盘"]
    for i, t in enumerate(transcript, start=1):
        if t.get("score") is None:
            continue
        lines += [
            f"**第 {i} 题（{t.get('dimension', '')}）：{t.get('title', '')}** — 得分 {t.get('score')}/10",
            f"- 问题：{t.get('question', '')}",
            f"- 亮点：{'；'.join(t.get('highlights', []) or ['—'])}",
            f"- 不足：{'；'.join(t.get('gaps', []) or ['—'])}",
            "",
        ]

    lines += [
        "## 5. 暴露出的能力短板",
        *([f"- {w}" for w in weak] or ["- 暂未发现明显系统性短板"]),
        "",
        "## 6. 最需要补的 3 个能力",
        *([f"- {w}" for w in weak[:3]] or ["- 继续保持，深化项目深度与量化表达"]),
        "",
        "## 7. 简历优化建议",
        "- 每段项目用 STAR 重写：背景-任务-行动-结果，结果尽量量化。",
        "- 把面试中答得吃力的点，提前在简历里补上佐证。",
        "",
        "## 8. 下次面试表达模板",
        "- 「我负责的是……（角色）；目标是……（指标）；我做了……（关键动作）；",
        "  最终结果是……（量化）；如果重来我会……（复盘）。」",
        "",
        "## 9. 7 天提升计划",
        "- Day1-2：复盘本次面试低分题，整理标准答案。",
        "- Day3-4：针对最弱维度做 2 个小项目/案例，沉淀量化结果。",
        "- Day5：重写简历项目段落。",
        "- Day6：找人模拟面试一次。",
        "- Day7：再跑一遍本系统的 AI 模拟面试，对比进步。",
        "",
        "---",
        "*本报告由 HR 提效智能体自动生成，仅供学习参考。*",
    ]
    return {"final_score": final_100, "report_markdown": "\n".join(lines),
            "dimension_avg": dim_avg}
