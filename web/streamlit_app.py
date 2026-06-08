"""HR 提效智能体 —— Streamlit 演示前端。

直接调用服务层（无需先启动 FastAPI），零基础也能一键演示：
    streamlit run web/streamlit_app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# 让 streamlit 能 import 到 app 包
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import engine, init_db  # noqa: E402
from app.llm_client import get_llm  # noqa: E402
from app.models import Application, Job, Resume  # noqa: E402
from app.services.interview_agent import (ask_next, finish_mock, start_mock,  # noqa: E402
                                         submit_answer)
from app.services.interview_planner import generate_plan  # noqa: E402
from app.services.report_exporter import (markdown_to_html,  # noqa: E402
                                          markdown_to_pdf_bytes,
                                          title_from_markdown)
from app.services.report_generator import (build_ranking_markdown,  # noqa: E402
                                           build_screening_markdown,
                                           export_job_package, export_ranking,
                                           ranking_dataframe)
from app.services.resume_extractor import extract_resume  # noqa: E402
from app.services.resume_parser import (parse_resume_bytes,  # noqa: E402
                                        parse_resume_text)
from app.services.screening_agent import (screen,  # noqa: E402
                                          screen_resumes_concurrently)
from sqlmodel import Session, func, select  # noqa: E402

st.set_page_config(page_title="HR 提效智能体", page_icon="🧑‍💼", layout="wide")
init_db()


# ---- 导出缓存（优化：避免每次 rerun 重复生成 PDF/ZIP；候选人数变化时自动失效）----
@st.cache_data(show_spinner=False)
def _cached_pdf(md: str) -> bytes:
    return markdown_to_pdf_bytes(md, title_from_markdown(md))


@st.cache_data(show_spinner=False)
def _cached_package(job_id: int, fmt: str, n_candidates: int) -> bytes:
    return export_job_package(job_id, fmt)


@st.cache_data(show_spinner=False)
def _ranking_excel_bytes(job_id: int, n_candidates: int) -> bytes:
    from pathlib import Path
    return Path(export_ranking(job_id, "excel")).read_bytes()


# ----------------------------- 公共工具 -----------------------------
def list_jobs():
    with Session(engine) as s:
        return s.exec(select(Job).order_by(Job.id.desc())).all()


def list_resumes():
    with Session(engine) as s:
        return s.exec(select(Resume).order_by(Resume.id.desc())).all()


def job_label(j: Job) -> str:
    return f"#{j.id} {j.job_title or '未命名岗位'}"


def llm_banner():
    llm = get_llm()
    if settings.offline_mode:
        st.info(f"🤖 当前为**离线 Mock 模式**（未配置 API Key），用内置规则模拟大模型，"
                f"流程完整可演示。配置 `.env` 中 `LLM_API_KEY` 即可切换真实大模型。", icon="ℹ️")
    else:
        st.success(f"🤖 已接入真实大模型：{llm.mode}", icon="✅")
    if getattr(llm, "last_error", None):
        st.warning(
            f"⚠️ 真实大模型上次调用失败，已**自动降级为离线 Mock**（结果由内置规则生成）。\n\n"
            f"错误：`{llm.last_error}`\n\n"
            f"若是 `Insufficient Balance`（余额不足），请给 API 账户充值；"
            f"或清空 `.env` 的 `LLM_API_KEY` 明确使用离线模式。修复后请重启网页。",
            icon="⚠️")


# ----------------------------- 侧边栏 -----------------------------
st.sidebar.title("🧑‍💼 HR 提效智能体")
st.sidebar.caption("简历筛选 · 面试官助手 · AI 模拟面试")
PAGE = st.sidebar.radio(
    "导航",
    ["① 首页 Dashboard", "② JD 管理", "③ 简历筛选",
     "④ 面试官助手", "⑤ AI 模拟面试", "⑥ 案例沉淀"],
)
st.sidebar.divider()
st.sidebar.caption(f"大模型模式：{get_llm().mode}")
st.sidebar.caption("⚠️ AI 仅辅助，不做最终录用决定")


# ============================ ① Dashboard ============================
if PAGE.startswith("①"):
    st.title("首页 Dashboard")
    st.write("面向 HR / 招聘负责人 / 面试官的 AI 提效系统。AI 自动读 JD、读简历、"
             "提取信息、评分、生成结论与面试提纲，并能作为面试官对你模拟面试。")
    llm_banner()
    with Session(engine) as s:
        n_jobs = s.exec(select(func.count()).select_from(Job)).one()
        n_res = s.exec(select(func.count()).select_from(Resume)).one()
        n_app = s.exec(select(func.count()).select_from(Application)).one()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("已上传 JD", n_jobs)
    c2.metric("已上传简历", n_res)
    c3.metric("已完成筛选", n_app)
    from app.models import InterviewSession
    with Session(engine) as s:
        n_int = s.exec(select(func.count()).select_from(InterviewSession)).one()
    c4.metric("已完成面试", n_int)

    st.divider()
    st.subheader("使用建议流程")
    st.markdown("""
1. **② JD 管理**：粘贴一份 JD → 解析成结构化字段。
2. **③ 简历筛选**：选 JD → 上传/粘贴简历 → 自动评分 → 看排序 → 下载报告。
3. **④ 面试官助手**：选 JD + 候选人 → 一键生成面试提纲与追问。
4. **⑤ AI 模拟面试**：输入 JD → AI 一次问一个问题面试你 → 生成提升报告。
""")

# ============================ ② JD 管理 ============================
elif PAGE.startswith("②"):
    st.title("JD 管理")
    llm_banner()
    default_jd = ""
    sample = ROOT / "data" / "sample_jd.md"
    if sample.exists():
        default_jd = sample.read_text(encoding="utf-8")

    jd_text = st.text_area("粘贴 JD 文本", value=default_jd, height=260,
                           placeholder="把岗位 JD 粘贴到这里……")
    if st.button("🔍 解析 JD", type="primary"):
        if not jd_text.strip():
            st.warning("请先粘贴 JD")
        else:
            with st.spinner("解析中……"):
                from app.services.jd_parser import parse_jd
                structured = parse_jd(jd_text)
                job = Job(
                    job_title=structured.get("job_title", ""),
                    department=structured.get("department", ""), jd_text=jd_text,
                    must_have_requirements=structured.get("must_have_requirements", []),
                    nice_to_have_requirements=structured.get("nice_to_have_requirements", []),
                    responsibilities=structured.get("responsibilities", []),
                    hard_skills=structured.get("hard_skills", []),
                    soft_skills=structured.get("soft_skills", []),
                    keywords=structured.get("keywords", []),
                    experience_requirements=structured.get("experience_requirements", ""),
                    education_requirements=structured.get("education_requirements", ""),
                    interview_focus=structured.get("interview_focus", []))
                with Session(engine) as s:
                    s.add(job)
                    s.commit()
                    s.refresh(job)
            st.success(f"已解析并保存为岗位 #{job.id}：{structured.get('job_title')}")
            st.json(structured)

    st.divider()
    st.subheader("已有岗位")
    jobs = list_jobs()
    if jobs:
        st.dataframe(pd.DataFrame(
            [{"ID": j.id, "岗位": j.job_title,
              "必备要求数": len(j.must_have_requirements or []),
              "硬技能": "、".join((j.hard_skills or [])[:6]),
              "创建时间": j.created_at} for j in jobs]),
            use_container_width=True, hide_index=True)
    else:
        st.caption("还没有岗位，先解析一份 JD 吧。")

# ============================ ③ 简历筛选 ============================
elif PAGE.startswith("③"):
    st.title("简历筛选")
    llm_banner()
    jobs = list_jobs()
    if not jobs:
        st.warning("请先到「② JD 管理」解析一份 JD。")
        st.stop()

    job = st.selectbox("选择岗位 JD", jobs, format_func=job_label)

    st.subheader("上传 / 粘贴简历")
    files = st.file_uploader("上传简历（支持 PDF / DOCX / TXT / MD，可多选）",
                             type=["pdf", "docx", "txt", "md"], accept_multiple_files=True)
    pasted = st.text_area("或直接粘贴一份简历文本", height=160)

    if st.button("🚀 解析并评分", type="primary"):
        # 先把所有输入读成纯文本（本地、快），再并发跑「抽取+评分+结论」
        items = []
        for f in files or []:
            items.append({"raw_text": parse_resume_bytes(f.read(), f.name),
                          "file_name": f.name})
        if pasted.strip():
            items.append({"raw_text": parse_resume_text(pasted),
                          "file_name": "pasted.txt"})

        if not items:
            st.warning("没有检测到简历输入。")
        else:
            import time
            t0 = time.time()
            with st.spinner(f"并发解析 + 评分 {len(items)} 份简历中……（真实模型约 20 秒/份，"
                            f"但多份同时进行，总耗时接近单份）"):
                results = screen_resumes_concurrently(job.id, items, max_workers=5)
            ok = [r for r in results if "error" not in r]
            err = [r for r in results if "error" in r]
            st.success(f"已完成 {len(ok)} 份，用时 {time.time()-t0:.1f} 秒"
                       f"（并发，非逐份累加）。")
            if err:
                st.warning(f"{len(err)} 份处理失败：" +
                           "；".join(f"{e.get('file_name','?')}: {e['error']}" for e in err))

    st.divider()
    st.subheader("候选人排序")
    df = ranking_dataframe(job.id)
    if not df.empty:
        rename = {"rank": "排名", "name": "姓名", "total_score": "总分", "level": "推荐等级",
                  "highest_education": "最高学历", "years_of_experience": "工作年限",
                  "core_skills": "核心技能", "main_strength": "主要优势",
                  "main_risk": "主要风险", "next_action": "建议下一步", "application_id": "应用ID"}
        st.dataframe(df.rename(columns=rename), use_container_width=True, hide_index=True)

        n_cand = len(df)
        st.markdown("**导出排序表**")
        rk_md = build_ranking_markdown(job.id)
        rc = st.columns(4)
        rc[0].download_button("⬇️ Excel", _ranking_excel_bytes(job.id, n_cand),
                              file_name=f"ranking_job{job.id}.xlsx",
                              mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        rc[1].download_button("⬇️ PDF", _cached_pdf(rk_md),
                              file_name=f"ranking_job{job.id}.pdf", mime="application/pdf")
        rc[2].download_button("⬇️ HTML", markdown_to_html(rk_md, "候选人排序表"),
                              file_name=f"ranking_job{job.id}.html", mime="text/html")
        rc[3].download_button("⬇️ Markdown", rk_md, file_name=f"ranking_job{job.id}.md")

        st.markdown("**📦 一键打包导出（排序表 + 全部候选人报告 → ZIP）**")
        pc1, pc2 = st.columns([1, 2])
        pkg_fmt = pc1.selectbox("包内格式", ["pdf", "html", "markdown"], key="pkg_fmt")
        with st.spinner(f"打包 {n_cand} 份报告中……"):
            pkg = _cached_package(job.id, pkg_fmt, n_cand)
        pc2.download_button(f"⬇️ 一键导出全部（{n_cand} 人，{pkg_fmt.upper()}）", pkg,
                            file_name=f"job_{job.id}_reports_{pkg_fmt}.zip",
                            mime="application/zip", type="primary")

        st.divider()
        st.subheader("查看 / 下载单份初筛报告")
        app_id = st.selectbox("选择候选人（应用ID）", df["application_id"].tolist(),
                              format_func=lambda x: f"应用#{x}")
        md = build_screening_markdown(int(app_id))
        title = title_from_markdown(md)
        with st.expander("预览报告"):
            st.markdown(md)
        d1, d2, d3 = st.columns(3)
        d1.download_button("⬇️ Markdown", md, file_name=f"screening_{app_id}.md")
        d2.download_button("⬇️ HTML", markdown_to_html(md, title),
                           file_name=f"screening_{app_id}.html", mime="text/html")
        d3.download_button("⬇️ PDF", markdown_to_pdf_bytes(md, title),
                           file_name=f"screening_{app_id}.pdf", mime="application/pdf")
    else:
        st.caption("还没有评分结果，先上传简历并点击「解析并评分」。")

# ============================ ④ 面试官助手 ============================
elif PAGE.startswith("④"):
    st.title("面试官助手（协助面试官模式）")
    llm_banner()
    jobs = list_jobs()
    if not jobs:
        st.warning("请先到「② JD 管理」解析一份 JD。")
        st.stop()
    job = st.selectbox("选择岗位 JD", jobs, format_func=job_label)

    resumes = list_resumes()
    resume = st.selectbox("选择候选人（可选）", [None] + resumes,
                          format_func=lambda r: "（不绑定具体候选人）" if r is None
                          else f"#{r.id} {r.candidate_name or r.file_name}")

    # 找到对应 application（如有）
    application_id = None
    if resume is not None:
        with Session(engine) as s:
            app = s.exec(select(Application).where(
                Application.job_id == job.id, Application.resume_id == resume.id)).first()
            application_id = app.id if app else None

    c1, c2 = st.columns(2)
    rnd = c1.selectbox("面试轮次", ["初面", "技术面", "业务面", "终面"])
    dur = c2.selectbox("面试时长（分钟）", [15, 30, 45, 60], index=1)

    if st.button("🧩 生成面试提纲", type="primary"):
        with st.spinner("生成中……"):
            plan = generate_plan(job.id, resume.id if resume else None,
                                 application_id, rnd, dur)
        st.success("面试提纲已生成（已保存到面试会话）")
        st.markdown(f"**面试目标：** {plan['interview_goal']}")
        st.markdown("**面试结构：**")
        for s_ in plan["interview_structure"]:
            st.markdown(f"- {s_}")
        st.markdown("### 提问清单")
        for i, q in enumerate(plan["question_list"], 1):
            with st.expander(f"第 {i} 题（{q['dimension']}）：{q['question'][:40]}…"):
                st.markdown(f"**问题：** {q['question']}")
                st.markdown(f"**为何要问：** {q['why_ask']}")
                st.markdown(f"**好的信号：** {'；'.join(q['good_answer_signals'])}")
                st.markdown(f"**差的信号：** {'；'.join(q['bad_answer_signals'])}")
                st.markdown(f"**追问：** {'；'.join(q['follow_up_questions'])}")
                st.markdown(f"**评分指引：** {q['score_guide']}")
        st.markdown("### 风险点核实问题")
        for q in plan["risk_verification_questions"]:
            st.markdown(f"- {q}")
        st.markdown("### 项目深挖问题")
        for q in plan["project_deep_dive_questions"]:
            st.markdown(f"- {q}")
        st.markdown("### 最终决策评分表")
        for q in plan["final_decision_rubric"]:
            st.markdown(f"- {q}")

# ============================ ⑤ AI 模拟面试 ============================
elif PAGE.startswith("⑤"):
    st.title("AI 模拟面试（输入 JD，AI 来面试你）")
    llm_banner()
    ss = st.session_state

    if "mock_session_id" not in ss:
        st.subheader("第一步：准备")
        default_jd = ""
        sample = ROOT / "data" / "sample_jd.md"
        if sample.exists():
            default_jd = sample.read_text(encoding="utf-8")
        jd_text = st.text_area("输入 JD", value=default_jd, height=200)
        resume_text = st.text_area("可选：粘贴你的简历", height=120)
        c1, c2 = st.columns(2)
        rnd = c1.selectbox("面试轮次", ["技术面", "初面", "业务面", "终面"])
        dur = c2.selectbox("时长（分钟）", [15, 30, 45, 60], index=1)
        if st.button("▶️ 开始模拟面试", type="primary"):
            if not jd_text.strip():
                st.warning("请先输入 JD")
            else:
                with st.spinner("AI 面试官准备中……"):
                    res = start_mock(jd_text=jd_text, resume_text=resume_text or None,
                                     interview_round=rnd, duration_minutes=dur)
                ss.mock_session_id = res["session_id"]
                ss.mock_max = res["max_questions"]
                ss.mock_current_q = res["question"]
                ss.mock_history = []
                ss.mock_finished = False
                ss.mock_report = None
                st.rerun()
    else:
        # 进行中
        st.caption(f"会话 #{ss.mock_session_id}　共 {ss.mock_max} 题")
        for h in ss.get("mock_history", []):
            with st.chat_message("assistant"):
                st.markdown(f"**第 {h['index']} 题（{h['dimension']}）**：{h['question']}")
            with st.chat_message("user"):
                st.markdown(h["answer"])
            fb = h["feedback"]
            with st.chat_message("assistant"):
                st.markdown(f"**本题得分：{fb['score']}/10**")
                if fb.get("highlights"):
                    st.markdown("亮点：" + "；".join(fb["highlights"]))
                if fb.get("gaps"):
                    st.markdown("不足：" + "；".join(fb["gaps"]))
                if fb.get("follow_up"):
                    st.markdown(f"追问：{fb['follow_up']}")

        if not ss.get("mock_finished"):
            q = ss.mock_current_q
            with st.chat_message("assistant"):
                st.markdown(f"### 第 {q['index']} 题：{q['title']}")
                st.markdown(f"**问题：** {q['question']}")
                st.markdown(f"**考察维度：** {q['dimension']}")
            answer = st.text_area("请你回答：", key=f"ans_{q['index']}", height=140)
            c1, c2 = st.columns([1, 1])
            if c1.button("提交回答", type="primary"):
                if not answer.strip():
                    st.warning("请先输入回答")
                else:
                    with st.spinner("AI 面试官点评中……"):
                        res = submit_answer(ss.mock_session_id, answer)
                    ss.mock_history.append({
                        "index": q["index"], "title": q["title"],
                        "dimension": q["dimension"], "question": q["question"],
                        "answer": answer, "feedback": res["feedback"]})
                    if res["should_finish"]:
                        ss.mock_finished = True
                    else:
                        ss.mock_current_q = ask_next(ss.mock_session_id)
                    st.rerun()
            if c2.button("结束并生成报告"):
                ss.mock_finished = True
                st.rerun()
        else:
            if ss.get("mock_report") is None:
                with st.spinner("生成面试报告中……"):
                    ss.mock_report = finish_mock(ss.mock_session_id)
            rep = ss.mock_report
            st.success(f"面试结束！综合得分：{rep['final_score']}/100")
            st.markdown(rep["report_markdown"])
            _md = rep["report_markdown"]
            _title = title_from_markdown(_md, "JD 模拟面试报告")
            _sid = ss.mock_session_id
            e1, e2, e3 = st.columns(3)
            e1.download_button("⬇️ Markdown", _md, file_name=f"interview_{_sid}.md")
            e2.download_button("⬇️ HTML", markdown_to_html(_md, _title),
                               file_name=f"interview_{_sid}.html", mime="text/html")
            e3.download_button("⬇️ PDF", markdown_to_pdf_bytes(_md, _title),
                               file_name=f"interview_{_sid}.pdf", mime="application/pdf")
            if st.button("🔄 再来一场"):
                for k in ["mock_session_id", "mock_max", "mock_current_q",
                          "mock_history", "mock_finished", "mock_report"]:
                    ss.pop(k, None)
                st.rerun()

# ============================ ⑥ 案例沉淀 ============================
elif PAGE.startswith("⑥"):
    st.title("案例沉淀")
    doc = ROOT / "docs" / "case_study.md"
    if doc.exists():
        st.markdown(doc.read_text(encoding="utf-8"))
    else:
        st.warning("docs/case_study.md 不存在。")
