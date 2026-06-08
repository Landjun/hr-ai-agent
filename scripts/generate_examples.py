# -*- coding: utf-8 -*-
"""生成 docs/examples/ 下的示例产出（离线 Mock 模式，确定性、免费、可复现）。

用法（项目根目录）：
    python scripts/generate_examples.py
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

# 用临时库 + 强制离线，保证可复现且不污染开发库
_t = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_t.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_t.name}"
os.environ["LLM_API_KEY"] = ""

from app.database import init_db, session_scope  # noqa: E402
from app.models import Job  # noqa: E402
from app.services.interview_agent import (ask_next, finish_mock,  # noqa: E402
                                         start_mock, submit_answer)
from app.services.jd_parser import parse_jd  # noqa: E402
from app.services.report_generator import build_screening_markdown  # noqa: E402
from app.services.screening_agent import process_one_resume, rank_for_job  # noqa: E402

EX = ROOT / "docs" / "examples"
EX.mkdir(parents=True, exist_ok=True)
HEADER = ("> 本文件由 `scripts/generate_examples.py` 在**离线 Mock 模式**下自动生成，"
          "用于展示系统输出格式。\n> 配置真实大模型后，证据与措辞会更丰富。\n\n")


def main() -> None:
    init_db()
    jd_text = (ROOT / "data" / "sample_jd_medical_pm.md").read_text(encoding="utf-8")
    jd = parse_jd(jd_text)
    with session_scope() as s:
        job = Job(job_title=jd["job_title"], jd_text=jd_text,
                  must_have_requirements=jd["must_have_requirements"],
                  hard_skills=jd["hard_skills"], keywords=jd["keywords"])
        s.add(job)
        s.flush()
        jid = job.id

    samples = ["sample_resume_medical_pm_strong.md",
               "sample_resume_medical_pm_weak.md", "sample_resume_1.md"]
    top = None
    for f in samples:
        raw = (ROOT / "data" / f).read_text(encoding="utf-8")
        res = process_one_resume(jid, raw, f)
        if top is None or res["total_score"] > top[1]:
            top = (res["application_id"], res["total_score"])

    # 1. 排序表
    rows = rank_for_job(jid)
    header = ["排名", "姓名", "总分", "推荐等级", "最高学历", "工作年限",
              "核心技能", "主要优势", "建议下一步"]
    keys = ["rank", "name", "total_score", "level", "highest_education",
            "years_of_experience", "core_skills", "main_strength", "next_action"]
    lines = ["# 候选人排序表（示例）", "", HEADER.strip(), "",
             "| " + " | ".join(header) + " |",
             "| " + " | ".join(["---"] * len(header)) + " |"]
    for r in rows:
        lines.append("| " + " | ".join(
            str(r.get(k, "")).replace("\n", " ") for k in keys) + " |")
    (EX / "ranking_sample.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 2. 头名初筛报告
    (EX / "screening_report_sample.md").write_text(
        HEADER + build_screening_markdown(top[0]), encoding="utf-8")

    # 3. AI 模拟面试报告
    start = start_mock(jd_text=jd_text, interview_round="技术面", duration_minutes=30)
    sid = start["session_id"]
    answers = [
        "我认为这个岗位最核心的是医疗行业理解 + AI 产品落地：既要懂临床流程和医院信息化，"
        "又要能把大模型能力变成可上线、可商业化的产品。",
        "我主导过 AI 医学影像辅助诊断系统，从 0 到 1 落地，在 12 家三甲医院上线，"
        "阅片效率提升 40%、漏诊率下降 25%、年营收新增 2000 万；难点是和算法团队建立标注与模型评测闭环。",
        "我会先和医生、算法、研发对齐目标和评测口径，用 MVP 快速验证，再用数据驱动迭代；"
        "最大的坑是早期标注标准不统一，我们后来建了标注规范和质检流程。",
        "失败经历：第一版问诊产品过度追求覆盖科室，导致每个科室深度不够、转化低。"
        "复盘后我们收敛到 3 个高频科室做深，转化明显提升。",
    ]
    finished, i = False, 0
    while not finished and i < len(answers):
        out = submit_answer(sid, answers[i])
        i += 1
        finished = out["should_finish"]
        if not finished and i < len(answers):
            ask_next(sid)
    report = finish_mock(sid)
    (EX / "interview_report_sample.md").write_text(
        HEADER + report["report_markdown"], encoding="utf-8")

    print("已生成：")
    for p in sorted(EX.glob("*.md")):
        if p.name != "README.md":
            print("  -", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
