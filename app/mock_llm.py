"""离线 Mock 大模型。

未配置 API Key 时，用「关键词匹配 + 规则启发式」模拟大模型的结构化输出，
让整条流水线在零配置下跑通。逻辑刻意保持可解释：每个判断都基于简历/JD 中
能找到的关键词作为证据，与「必须输出证据、不许编造」的安全要求一致。

⚠️ Mock 只是演示与兜底，真实评估请配置 LLM_API_KEY 使用真实大模型。
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

# 常见技术 / 能力关键词词典（用于技能命中与证据提取）
SKILL_KEYWORDS = [
    "python", "java", "go", "golang", "c++", "javascript", "typescript", "sql",
    "fastapi", "flask", "django", "streamlit", "vue", "react",
    "llm", "大模型", "rag", "agent", "智能体", "langchain", "coze", "扣子", "dify",
    "prompt", "提示词", "微调", "finetune", "向量", "embedding", "知识库",
    "nlp", "机器学习", "深度学习", "pytorch", "tensorflow", "transformer",
    "docker", "k8s", "kubernetes", "linux", "git", "ci/cd", "微服务",
    "mysql", "postgres", "redis", "mongodb", "elasticsearch", "kafka",
    "数据分析", "数据清洗", "pandas", "spark", "hadoop", "数仓", "etl",
    "产品", "需求", "原型", "axure", "用户研究", "数据驱动", "增长", "转化",
    "项目管理", "敏捷", "scrum", "跨部门", "协作", "复盘", "指标", "okr", "kpi",
    "飞书", "多维表格", "工作流", "自动化", "api", "对接", "部署", "上线",
    # 产品经理通用
    "产品经理", "prd", "竞品", "竞品分析", "需求分析", "用户画像", "mvp", "迭代",
    "商业化", "gmv", "dau", "mau", "留存", "转化率", "a/b", "数据中台", "路演",
    "tob", "toc", "tog", "to b", "to c", "to g", "0到1", "从0到1", "从 0 到 1",
    # 医疗 / 医疗 AI
    "医疗", "医学", "医院", "影像", "病理", "诊断", "辅助诊断", "智能问诊", "随访",
    "电子病历", "his", "临床", "临床试验", "院内", "医院信息化", "医保", "处方",
    "合规", "注册证", "三类证", "nmpa", "药监", "标注", "数据标注", "cv", "计算机视觉",
]

EDU_KEYWORDS = ["博士", "硕士", "本科", "大专", "专科", "研究生", "学士", "mba"]
GOOD_SCHOOL = ["清华", "北大", "985", "211", "复旦", "上海交大", "浙大", "南大",
               "中科院", "人民大学", "双一流", "一流大学"]

# 岗位专属维度 → 关键词桶（用于通用维度的证据匹配，便于扩展到不同岗位）
_DIM_KEYWORDS = {
    "医疗行业理解": ["医疗", "医学", "医院", "临床", "电子病历", "his", "医保", "合规",
                "注册证", "三类证", "nmpa", "药监", "影像", "病理", "诊断", "随访",
                "院内", "医院信息化", "处方", "辅助诊断", "智能问诊"],
    "ai产品能力": ["大模型", "llm", "ai", "智能体", "agent", "rag", "算法", "数据",
              "标注", "数据标注", "cv", "计算机视觉", "nlp", "辅助诊断", "智能问诊",
              "embedding", "知识库", "prompt", "影像"],
    "产品方法论": ["产品", "prd", "需求", "需求分析", "原型", "竞品", "竞品分析",
              "用户研究", "用户画像", "mvp", "迭代", "数据驱动", "axure", "路演"],
    "跨部门协作与推动": ["跨部门", "协作", "推动", "落地", "医生", "研发", "运营",
                 "项目管理", "敏捷", "scrum", "对接"],
}

PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
YEARS_RE = re.compile(r"(\d{1,2})\s*年.{0,6}(经验|工作)")


# ---------------------------------------------------------------------------
# 公共工具
# ---------------------------------------------------------------------------
def _find_skills(text: str) -> List[str]:
    low = text.lower()
    hits = []
    for kw in SKILL_KEYWORDS:
        if kw.lower() in low and kw not in hits:
            hits.append(kw)
    return hits


def _lines(text: str) -> List[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 1. JD 解析
# ---------------------------------------------------------------------------
def _jd_parse(payload: Dict[str, Any]) -> str:
    text = payload.get("jd_text", "")
    lines = _lines(text)
    title = ""
    for ln in lines:
        m = re.search(r"(?:招聘)?(?:岗位|职位)[:：]\s*(.+)", ln)
        if m:
            title = m.group(1).strip()
            break
    if not title and lines:
        title = lines[0][:30]

    def _is_header(s: str) -> bool:
        # 形如「任职要求（必须满足）：」「加分项：」这类小标题，去掉
        return bool(re.search(r"[：:]\s*$", s)) and len(s) < 16

    def _clean(s: str) -> str:
        return s.lstrip("-•· 0123456789.、")

    must, nice, resp = [], [], []
    section = ""  # 当前所属小节：must / nice / resp
    for ln in lines:
        # 标题行用于切换小节，本身不计入内容
        if "加分" in ln or "优先" in ln:
            section = "nice"
            if _is_header(ln):
                continue
        elif "职责" in ln or ("负责" in ln and _is_header(ln)):
            section = "resp"
            if _is_header(ln):
                continue
        elif "任职要求" in ln or "岗位要求" in ln or ("要求" in ln and _is_header(ln)):
            section = "must"
            if _is_header(ln):
                continue
        if _is_header(ln):
            continue

        content = _clean(ln)
        # 优先按所在小节归类；小节未知时回退到关键词判断
        if section == "nice" or any(k in ln for k in ["加分", "优先", "nice", "更佳"]):
            nice.append(content)
        elif section == "resp" or any(k in ln for k in ["负责", "完成", "推动", "搭建"]):
            resp.append(content)
        elif section == "must" or any(k in ln for k in ["必须", "要求", "熟悉", "精通", "掌握", "具备", "经验"]):
            must.append(content)

    skills = _find_skills(text)
    edu = ""
    for k in EDU_KEYWORDS:
        if k in text:
            edu = f"{k}及以上"
            break
    ym = YEARS_RE.search(text)
    exp = f"{ym.group(1)}年及以上相关经验" if ym else ""

    result = {
        "job_title": title or "未命名岗位",
        "department": "",
        "must_have_requirements": must[:8] or ["（JD 未明确列出硬性要求，请人工补充）"],
        "nice_to_have_requirements": nice[:6],
        "responsibilities": resp[:8],
        "hard_skills": skills,
        "soft_skills": [s for s in ["沟通表达", "团队协作", "项目管理", "复盘"] if s in text],
        "experience_requirements": exp,
        "education_requirements": edu,
        "keywords": skills[:15],
        "interview_focus": (skills[:3] + ["项目深挖", "结果与复盘"])[:5],
    }
    return _dumps(result)


# ---------------------------------------------------------------------------
# 2. 简历信息抽取
# ---------------------------------------------------------------------------
def _section(text: str, names: List[str]) -> str:
    """粗略截取某个标题段落的文本。"""
    lines = text.splitlines()
    out, capturing = [], False
    for ln in lines:
        s = ln.strip()
        if any(n in s for n in names) and len(s) < 20:
            capturing = True
            continue
        if capturing:
            # 遇到下一个明显的标题就停止
            if s and len(s) < 12 and any(h in s for h in
                                         ["工作经", "项目经", "教育", "技能", "自我评价", "证书", "荣誉"]) \
                    and not any(n in s for n in names):
                break
            out.append(ln)
    return "\n".join(out).strip()


def _resume_extract(payload: Dict[str, Any]) -> str:
    text = payload.get("raw_text", "")
    lines = _lines(text)

    phone_m = PHONE_RE.search(text)
    email_m = EMAIL_RE.search(text)

    # 姓名：取靠前的一个 2~4 字中文短行，或「姓名:」后内容
    _name_headers = {"个人优势", "工作经历", "工作经验", "项目经历", "项目经验", "教育背景",
                     "专业技能", "自我评价", "求职意向", "基本信息", "联系方式", "个人简历",
                     "个人信息", "教育经历", "实习经历", "荣誉奖项"}
    name = ""
    for ln in lines[:8]:
        m = re.search(r"姓\s*名[:：]?\s*([一-龥]{2,4})", ln)
        if m:
            name = m.group(1)
            break
    if not name:
        for ln in lines[:5]:
            if re.fullmatch(r"[一-龥]{2,4}", ln):
                name = ln
                break
    if not name:
        # 兜底：带水印噪声的 PDF，姓名常被包裹成「_ _ 陈志国 _ _」，
        # 取该行去掉非中文后的 2-4 字中文（排除常见小标题）
        for ln in lines[:6]:
            cjk = "".join(re.findall(r"[一-龥]", ln))
            if 2 <= len(cjk) <= 4 and cjk not in _name_headers and "：" not in ln:
                name = cjk
                break

    education, school, major = "", "", ""
    for k in ["博士", "硕士", "研究生", "本科", "大专", "专科", "MBA"]:
        if k in text:
            education = k
            break
    for s in GOOD_SCHOOL + ["大学", "学院"]:
        m = re.search(r"([一-龥]{2,8}(大学|学院))", text)
        if m:
            school = m.group(1)
            break
    mm = re.search(r"专业[:：]?\s*([一-龥]{2,12})", text)
    if mm:
        major = mm.group(1)

    ym = YEARS_RE.search(text)
    years = ym.group(1) + "年" if ym else ""

    skills = _find_skills(text)

    work_sec = _section(text, ["工作经历", "工作经验"])
    proj_sec = _section(text, ["项目经历", "项目经验"])
    self_eval = _section(text, ["自我评价", "个人评价", "自我介绍"])

    # 粗粒度的经历拆分：以公司/项目名行作为分隔
    def split_blocks(sec: str) -> List[str]:
        blocks, cur = [], []
        for ln in sec.splitlines():
            if re.search(r"(20\d{2})", ln) and cur:
                blocks.append("\n".join(cur).strip())
                cur = [ln]
            else:
                cur.append(ln)
        if cur:
            blocks.append("\n".join(cur).strip())
        return [b for b in blocks if b][:4]

    work_experiences = []
    for b in split_blocks(work_sec):
        comp = re.search(r"([一-龥A-Za-z]{2,20}(公司|科技|集团|医院|银行|有限))", b)
        work_experiences.append({
            "company": comp.group(1) if comp else "（无法判断）",
            "position": "", "start_date": "", "end_date": "",
            "description": b[:200],
        })

    project_experiences = []
    for b in split_blocks(proj_sec):
        project_experiences.append({
            "project_name": b.splitlines()[0][:30] if b.splitlines() else "项目",
            "role": "", "start_date": "", "end_date": "",
            "description": b[:300],
            "tech_stack": _find_skills(b),
            "achievements": [ln.strip() for ln in b.splitlines()
                             if any(c in ln for c in ["提升", "降低", "增长", "%", "万", "倍"])][:3],
        })

    result = {
        "name": name or "无",
        "gender": "男" if "男" in text[:200] else ("女" if "女" in text[:200] else "无"),
        "age": (re.search(r"(\d{2})\s*岁", text).group(1) if re.search(r"(\d{2})\s*岁", text) else "无"),
        "phone": phone_m.group(1) if phone_m else "无",
        "email": email_m.group(0) if email_m else "无",
        "highest_education": education or "无",
        "school": school or "无",
        "major": major or "无",
        "years_of_experience": years or "无",
        "expected_position": (re.search(r"求职意向[:：]?\s*(.+)", text).group(1).strip()[:30]
                              if re.search(r"求职意向[:：]?\s*(.+)", text) else "无"),
        "expected_salary": (re.search(r"期望薪资[:：]?\s*(.+)", text).group(1).strip()[:20]
                            if re.search(r"期望薪资[:：]?\s*(.+)", text) else "无"),
        "expected_city": (re.search(r"期望城市[:：]?\s*([一-龥]{2,8})", text).group(1)
                          if re.search(r"期望城市[:：]?\s*([一-龥]{2,8})", text) else "无"),
        "skills": skills,
        "work_experiences": work_experiences,
        "project_experiences": project_experiences,
        "self_evaluation": self_eval[:300] or "无",
        "raw_text": text,
    }
    return _dumps(result)


# ---------------------------------------------------------------------------
# 3. 简历评分（按维度产出 score/evidence/risk/reason）
# ---------------------------------------------------------------------------
def _resume_score(payload: Dict[str, Any]) -> str:
    jd = payload.get("jd", {})
    resume = payload.get("resume", {})
    dimensions = payload.get("dimensions", [])  # [{dimension, max_score, ...}]

    resume_text = (resume.get("raw_text", "") or "").lower()
    resume_skills = [s.lower() for s in resume.get("skills", [])]
    jd_must = jd.get("must_have_requirements", [])
    jd_skills = [s.lower() for s in jd.get("hard_skills", [])]
    jd_keywords = [s.lower() for s in jd.get("keywords", [])] or jd_skills

    def match_ratio(targets: List[str]) -> tuple[float, List[str], List[str]]:
        hit, miss = [], []
        for t in targets:
            tl = t.lower()
            if tl and (tl in resume_text or tl in resume_skills
                       or any(tl in s or s in tl for s in resume_skills)):
                hit.append(t)
            else:
                miss.append(t)
        ratio = len(hit) / len(targets) if targets else 0.5
        return ratio, hit, miss

    results = []
    for d in dimensions:
        dim = d["dimension"]
        maxs = float(d["max_score"])
        evidence, risk, reason, ratio = [], [], "", 0.5

        if dim == "必备技能匹配":
            ratio, hit, miss = match_ratio(jd_skills or jd_keywords)
            evidence = [f"简历命中技能：{h}" for h in hit[:6]] or ["未在简历中检索到 JD 硬技能关键词"]
            risk = [f"未见证据：{m}" for m in miss[:5]]
            reason = f"JD 硬技能 {len(jd_skills or jd_keywords)} 项，命中 {len(hit)} 项。"
        elif dim == "岗位匹配度":
            ratio, hit, miss = match_ratio(jd_keywords)
            evidence = [f"方向关键词命中：{h}" for h in hit[:6]] or ["简历与 JD 方向关键词重合较少"]
            risk = [f"缺少：{m}" for m in miss[:4]]
            reason = f"JD 关键词整体命中率 {ratio:.0%}。"
        elif dim == "项目经验匹配":
            projs = resume.get("project_experiences", [])
            ratio = min(1.0, len(projs) / 2.0) * (0.6 + 0.4 * match_ratio(jd_skills or jd_keywords)[0])
            evidence = [f"项目：{p.get('project_name', '')}" for p in projs[:3]] or ["简历中未明确列出项目经历"]
            ach = [a for p in projs for a in p.get("achievements", [])]
            if ach:
                evidence += [f"量化结果：{a}" for a in ach[:2]]
            else:
                risk.append("项目缺少量化结果/复盘证据，建议面试追问")
            reason = f"识别到 {len(projs)} 段项目经历。"
        elif dim == "工作经历匹配":
            works = resume.get("work_experiences", [])
            ratio = min(1.0, len(works) / 2.0)
            evidence = [f"公司：{w.get('company', '')}" for w in works[:3]] or ["简历中工作经历信息不足"]
            yrs = resume.get("years_of_experience", "无")
            reason = f"识别到 {len(works)} 段工作经历，工作年限：{yrs}。"
        elif dim == "教育背景":
            edu = resume.get("highest_education", "无")
            school = resume.get("school", "无")
            base = {"博士": 1.0, "硕士": 0.9, "研究生": 0.9, "本科": 0.8}.get(edu, 0.6)
            if any(g in school for g in GOOD_SCHOOL):
                base = min(1.0, base + 0.1)
                evidence.append(f"院校亮点：{school}")
            ratio = base
            evidence.append(f"最高学历：{edu}；院校：{school}")
            reason = "学历/院校仅在 JD 明确要求时作为匹配项，不作歧视性判断。"
        elif dim == "稳定性与表达质量":
            works = resume.get("work_experiences", [])
            ratio = 0.85 if len(works) <= 3 else 0.6
            if len(works) > 3:
                risk.append("工作经历较多，需在面试中核实跳槽原因（仅核实，不预设负面）")
            evidence.append("简历结构完整、字段可提取" if resume.get("name", "无") != "无"
                            else "简历信息缺失较多，表达质量待核实")
            reason = "综合跳槽频率与简历表达完整度评估。"
        elif dim == "加分项":
            bonus = [k for k in ["开源", "论文", "专利", "竞赛", "获奖", "github", "博客",
                                 "mba", "证书", "医学背景", "临床背景"] if k in resume_text]
            ratio = min(1.0, len(bonus) / 3.0)
            evidence = [f"加分信号：{b}" for b in bonus] or ["未发现明显加分项"]
            reason = f"检索到 {len(bonus)} 个加分信号。"
        elif dim == "项目与商业化结果":
            projs = resume.get("project_experiences", [])
            quant = [ln for ln in resume_text.split("\n")
                     if any(c in ln for c in ["%", "万", "倍", "增长", "转化", "gmv",
                                              "dau", "留存", "营收", "提升", "下降"])]
            biz = [k for k in ["商业化", "0到1", "从0到1", "从 0 到 1", "上线", "落地",
                               "盈利", "营收", "付费"] if k in resume_text]
            ratio = min(1.0, 0.4 * min(1.0, len(projs) / 2.0)
                        + 0.35 * min(1.0, len(quant) / 2.0)
                        + 0.25 * min(1.0, len(biz) / 2.0))
            evidence = [f"项目：{p.get('project_name', '')}" for p in projs[:2]]
            evidence += [f"量化/商业化：{q.strip()[:40]}" for q in quant[:2]]
            if biz:
                evidence.append("商业化信号：" + "、".join(biz[:4]))
            if not quant:
                risk.append("缺少量化结果，建议面试追问具体指标与商业化数据")
            reason = f"识别项目 {len(projs)} 段、量化句 {len(quant)} 处、商业化信号 {len(biz)} 个。"
        elif dim.lower() in _DIM_KEYWORDS:
            bucket = _DIM_KEYWORDS[dim.lower()]
            hit = [k for k in bucket if k in resume_text]
            ratio = min(1.0, len(hit) / max(3, len(bucket) * 0.4))
            evidence = [f"命中：{h}" for h in hit[:6]] or [f"简历中较少出现「{dim}」相关证据"]
            if len(hit) < 2:
                risk.append(f"{dim}相关证据不足，需人工/面试核实")
            reason = f"在简历中命中「{dim}」相关关键词 {len(hit)} 个。"
        else:
            ratio, _, _ = match_ratio(jd_keywords)
            reason = "通用维度按 JD 关键词命中率评估。"

        score = round(maxs * max(0.0, min(1.0, ratio)), 1)
        if not evidence:
            evidence = ["（无法判断，建议人工复核）"]
        results.append({
            "dimension": dim,
            "score": score,
            "max_score": maxs,
            "evidence": evidence,
            "risk": risk,
            "reason": reason + "（离线 Mock 评分，仅供演示）",
        })
    return _dumps(results)


# ---------------------------------------------------------------------------
# 4. 筛选结论（总分 + 等级 + 优势/风险/建议问题）
# ---------------------------------------------------------------------------
def _screening_decision(payload: Dict[str, Any]) -> str:
    dim_scores = payload.get("dimension_scores", [])
    jd = payload.get("jd", {})
    resume = payload.get("resume", {})
    total = round(sum(d.get("score", 0) for d in dim_scores), 1)

    if total >= 85:
        level = "强烈推荐面试"
    elif total >= 70:
        level = "建议面试"
    elif total >= 60:
        level = "备选"
    else:
        level = "暂不推荐"

    strengths, risks, missing = [], [], []
    for d in dim_scores:
        if d.get("max_score") and d["score"] / d["max_score"] >= 0.8:
            strengths += d.get("evidence", [])[:1]
        if d.get("max_score") and d["score"] / d["max_score"] < 0.5:
            risks.append(f"{d['dimension']}偏弱：{d.get('reason', '')}")
        missing += d.get("risk", [])

    questions = []
    for p in resume.get("project_experiences", [])[:2]:
        questions.append(f"请展开讲一下「{p.get('project_name', '某项目')}」的背景、你的具体动作、遇到的最大难点和最终结果。")
    for s in jd.get("hard_skills", [])[:2]:
        questions.append(f"JD 要求 {s}，请举一个你用 {s} 解决实际问题的例子，越具体越好。")
    if not questions:
        questions = ["请用 STAR 结构介绍一个你最有代表性的项目。"]

    result = {
        "total_score": total,
        "level": level,
        "summary": f"候选人 {resume.get('name', '该候选人')} 总分 {total}，{level}。"
                   f"优势集中在高分维度，风险点需在面试中核实。仅供 HR 辅助参考，最终由人工确认。",
        "strengths": strengths[:6] or ["（暂无突出优势，建议人工复核）"],
        "risks": risks[:6] or ["无明显高风险维度"],
        "missing_requirements": [m for m in missing if "未见" in m or "缺少" in m][:6],
        "suggested_interview_questions": questions[:5],
        "manual_review_needed": True,
    }
    return _dumps(result)


# ---------------------------------------------------------------------------
# 5. 面试官提纲（模式 A）
# ---------------------------------------------------------------------------
def _interview_plan(payload: Dict[str, Any]) -> str:
    jd = payload.get("jd", {})
    resume = payload.get("resume", {})
    rnd = payload.get("interview_round", "初面")
    duration = payload.get("duration_minutes", 30)
    skills = jd.get("hard_skills", []) or jd.get("keywords", [])
    projects = resume.get("project_experiences", [])

    questions = []
    for s in skills[:3]:
        questions.append({
            "question": f"你简历提到接触过 {s}，请讲一个你用它解决真实问题的完整案例。",
            "dimension": "硬技能深度",
            "why_ask": f"JD 把 {s} 列为关键要求，需要验证是真实掌握还是仅了解。",
            "good_answer_signals": ["能讲清场景与取舍", "有量化结果", "能说出踩过的坑"],
            "bad_answer_signals": ["只停留在名词概念", "说不出自己具体做了什么"],
            "follow_up_questions": [f"如果 {s} 换成另一种方案，你会怎么选？", "上线后效果如何衡量？"],
            "score_guide": "1-3 只知概念 / 4-7 能落地 / 8-10 有深度且能复盘",
        })
    for p in projects[:2]:
        questions.append({
            "question": f"请用 STAR 拆解「{p.get('project_name', '该项目')}」：背景、你的角色、最难的点、结果。",
            "dimension": "项目深挖",
            "why_ask": "简历项目描述较概括，需要核实候选人的真实贡献。",
            "good_answer_signals": ["能区分团队成果与个人贡献", "难点真实", "有复盘"],
            "bad_answer_signals": ["全程用『我们』", "讲不出难点", "结果含糊"],
            "follow_up_questions": ["这个项目你最大的失误是什么？", "再来一次你会怎么改？"],
            "score_guide": "看个人贡献清晰度与复盘深度打分",
        })

    result = {
        "interview_goal": f"在 {duration} 分钟{rnd}中，验证候选人与 JD 的关键匹配点，"
                          f"重点核实简历中『看起来强但证据不足』之处。",
        "interview_structure": [
            "1) 开场与暖场（2 分钟）",
            "2) 项目深挖（核心，占一半时间）",
            "3) 硬技能验证",
            "4) 风险点核实",
            "5) 候选人提问与收尾",
        ],
        "question_list": questions or [{
            "question": "请介绍你最有代表性的一段经历。", "dimension": "综合",
            "why_ask": "信息不足时的兜底开场问题。",
            "good_answer_signals": ["结构清晰"], "bad_answer_signals": ["泛泛而谈"],
            "follow_up_questions": ["最难的点是什么？"], "score_guide": "STAR 完整度",
        }],
        "risk_verification_questions": [
            "简历中某些能力缺少项目佐证，请补充具体例子。",
            "工作衔接 / 空窗期是否方便说明？（仅核实事实，不作预设判断）",
        ],
        "project_deep_dive_questions": [
            "这个项目的目标和最终业务结果分别是什么？",
            "你个人承担了哪部分？哪些是你独立完成的？",
            "过程中最大的技术 / 协作难点，你是怎么解决的？",
        ],
        "final_decision_rubric": [
            "硬技能：是否达到岗位要求的实操水平",
            "项目深度：个人贡献与复盘能力",
            "沟通表达：逻辑结构是否清晰",
            "综合建议：通过 / 备选 / 不通过（附理由，最终由人工确认）",
        ],
    }
    return _dumps(result)


# ---------------------------------------------------------------------------
# 6. AI 模拟面试：一次只问一个问题
# ---------------------------------------------------------------------------
def _interview_question(payload: Dict[str, Any]) -> str:
    jd = payload.get("jd", {})
    index = payload.get("index", 1)
    asked = payload.get("asked_titles", [])
    skills = jd.get("hard_skills", []) or jd.get("keywords", []) or ["岗位理解"]

    bank = [
        ("岗位理解", "结合这份 JD，你认为这个岗位最核心的 1-2 个能力要求是什么？为什么？", "岗位理解"),
    ]
    for s in skills[:4]:
        bank.append((f"{s} 实操", f"请讲一个你用 {s} 解决真实问题的完整案例：背景、你的动作、结果。", "硬技能"))
    bank.append(("项目深挖", "请用 STAR 结构，详细拆解你最有代表性的一个项目。", "项目经验"))
    bank.append(("难点复盘", "讲一个你失败或踩坑的经历，你从中学到了什么？", "复盘能力"))

    idx = min(index - 1, len(bank) - 1)
    while idx < len(bank) - 1 and bank[idx][0] in asked:
        idx += 1
    title, q, dim = bank[idx]

    result = {"index": index, "title": title, "question": q, "dimension": dim}
    return _dumps(result)


def _answer_feedback(payload: Dict[str, Any]) -> str:
    answer = (payload.get("answer", "") or "").strip()
    n = len(answer)
    has_number = bool(re.search(r"\d", answer))
    has_star = any(k in answer for k in ["背景", "目标", "负责", "结果", "因为", "所以", "提升", "降低"])

    if n < 15 or answer in {"不知道", "不会", "没有"}:
        score = 2.0
        result = {
            "score": score,
            "highlights": [],
            "gaps": ["回答过于简短/空泛，几乎没有可评估的信息"],
            "follow_up": "可以先别急着下结论——哪怕举一个小例子也好，你具体做过什么？",
            "move_on": False,
        }
        return _dumps(result)

    score = 5.0
    highlights, gaps = [], []
    if has_number:
        score += 2
        highlights.append("有量化数据，可信度较高")
    else:
        gaps.append("缺少量化结果，建议补充具体数字")
    if has_star:
        score += 1.5
        highlights.append("回答有结构，能看到动作与结果")
    else:
        gaps.append("结构不够清晰，建议用 STAR（背景-任务-行动-结果）组织")
    if n > 120:
        score += 0.5
        highlights.append("信息量充足")

    score = round(min(10.0, score), 1)
    result = {
        "score": score,
        "highlights": highlights or ["有一定信息量"],
        "gaps": gaps or ["可以再深入一层细节"],
        "follow_up": "你提到的这个结果，是怎么衡量出来的？过程中最大的难点是什么？" if score < 8
                     else "回答得不错，再问一个进阶问题：如果资源减半，你会怎么取舍？",
        "move_on": score >= 7.0,
    }
    return _dumps(result)


# ---------------------------------------------------------------------------
# 路由分发
# ---------------------------------------------------------------------------
def _score_and_decide(payload: Dict[str, Any]) -> str:
    """合并版：一次产出『维度评分 + 筛选结论』。复用打分与结论两个 Mock 并合并。"""
    dim_scores = json.loads(_resume_score(payload))
    decision = json.loads(_screening_decision({**payload, "dimension_scores": dim_scores}))
    decision["dimension_scores"] = dim_scores
    return _dumps(decision)


_DISPATCH = {
    "jd_parse": _jd_parse,
    "resume_extract": _resume_extract,
    "resume_score": _resume_score,
    "screening_decision": _screening_decision,
    "score_and_decide": _score_and_decide,
    "interview_plan": _interview_plan,
    "interview_question": _interview_question,
    "answer_feedback": _answer_feedback,
}


def generate(task: str, payload: Dict[str, Any]) -> str:
    fn = _DISPATCH.get(task)
    if fn is None:
        return _dumps({"error": f"未知 Mock 任务: {task}"})
    return fn(payload)
