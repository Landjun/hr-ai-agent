# HR 提效智能体（HR AI Agent）

> 面向 **HR / 招聘负责人 / 面试官** 的 AI 提效系统。
> 自动读 JD、读简历、抽取结构化信息、按规则**带证据地**评分、生成筛选结论与面试提纲，
> 还能作为 **AI 面试官** 对你进行模拟面试并生成提升报告。
>
> 核心理念：**AI 只做辅助判断，不做最终录用决定；每个判断都要有证据、可追溯。**

---

## 1. 这是什么 / 解决什么问题

招聘初筛痛点：简历格式杂、人工录入慢、打分凭感觉、标准不统一、淘汰说不清理由、
面试提纲临时拍脑袋、候选人数据散落无法沉淀。

本项目把这些环节自动化：

- **第一版 · 简历筛选智能体**：JD 解析 → 简历抽取 → 7 维结构化评分（每维有证据/风险）
  → 筛选结论 → 候选人排序 → 一键导出 Excel/Markdown/JSON 报告。
- **第二版 · 协助面试官智能体**
  - 模式 A：为面试官生成结构化面试提纲（含追问与评分指引）。
  - 模式 B：输入 JD，AI **一次只问一个问题**地面试你，最后生成「面试报告 + 7 天提升计划」。

> ✨ **零配置即可运行**：不填任何 API Key 时，系统自动进入「离线 Mock 模式」，
> 用内置规则模拟大模型，整条流水线照常跑通、可演示。填了 Key 就自动切换真实大模型。

---

## 2. 技术栈

Python 3.10+ · FastAPI · Streamlit · SQLite · SQLModel · Pydantic ·
python-docx / pdfplumber / pypdf · pandas / openpyxl · OpenAI 兼容 SDK（DeepSeek/通义/OpenAI）· pytest

---

## 3. 安装

```bash
pip install -r requirements.txt
```

## 4. 配置 API Key（可选）

```bash
# Windows PowerShell:  Copy-Item .env.example .env
cp .env.example .env
```

编辑 `.env`：
- **想零配置演示** → 什么都不用填，保持 `LLM_API_KEY=` 为空即可（离线 Mock）。
- **想用真实大模型** → 填入 `LLM_API_KEY`，并按提供方设置 `LLM_BASE_URL` / `LLM_MODEL`：

| 提供方 | LLM_BASE_URL | LLM_MODEL |
| --- | --- | --- |
| DeepSeek | https://api.deepseek.com/v1 | deepseek-chat |
| OpenAI | https://api.openai.com/v1 | gpt-4o-mini |
| 通义千问 | https://dashscope.aliyuncs.com/compatible-mode/v1 | qwen-plus |

> 🔒 API Key 只放 `.env`，绝不写死在代码里，`.env` 已在 `.gitignore` 中。

## 5. 运行

**方式一（推荐演示）：只跑前端，直接调用服务层，无需启动后端**

```bash
streamlit run web/streamlit_app.py
```

**方式二：跑后端 API（提供 REST 接口 / Swagger 文档）**

```bash
python run.py
# 打开 http://127.0.0.1:8000/docs 查看交互式 API 文档
```

两者可同时运行。数据库与默认评分规则会在首次启动时自动创建。

---

## 6. 怎么用

### 第一版 · 简历筛选
1. 「② JD 管理」粘贴 JD → 解析（已预填样例 JD）。
2. 「③ 简历筛选」选 JD → 上传/粘贴简历（PDF/DOCX/TXT/MD）→ 解析并评分。
3. 看候选人排序表 → 生成单人初筛报告 → 导出 Excel/Markdown/JSON。

### 第二版 · 面试
4. 「④ 面试官助手」选 JD + 候选人 + 轮次/时长 → 生成面试提纲。
5. 「⑤ AI 模拟面试」输入 JD（可选简历）→ 开始 → AI 一次问一题 → 结束生成报告。

### 导出报告
- 排序表：`③ 简历筛选` 页的导出按钮，或 API `GET /reports/ranking/{job_id}?fmt=excel`。
- 初筛报告：页面下载，或 API `GET /reports/screening/{application_id}`。
- 面试报告：模拟面试结束后下载，或 API `GET /reports/interview/{session_id}`。
- 文件默认输出到 `outputs/`。

---

## 7. 项目结构

```
hr-ai-agent/
├── README.md / requirements.txt / .env.example / run.py
├── app/
│   ├── config.py          # 配置（含离线 Mock 判定）
│   ├── database.py        # 建表 + 默认评分规则
│   ├── models.py          # 7 张 SQLModel 表
│   ├── schemas.py         # Pydantic 结构化契约
│   ├── llm_client.py      # OpenAI 兼容客户端（含离线路由）
│   ├── mock_llm.py        # 离线 Mock 启发式引擎
│   ├── services/          # JD/简历/评分/筛选/面试/报告 服务
│   ├── prompts/           # 7 个 prompt（.md）
│   ├── routers/           # FastAPI 路由
│   └── utils/             # 文件读取/清洗/JSON/评分换算
├── web/streamlit_app.py   # 6 页演示前端
├── data/                  # 样例 JD/简历 + scoring_rules.json
├── docs/                  # 案例/工作流/表/Prompt/演示 文档
├── outputs/               # 报告产出
└── tests/                 # pytest（离线可跑）
```

## 8. 测试

```bash
pytest -q
```

全部用例离线可跑（强制 Mock 模式 + 临时数据库），覆盖：简历抽取、JD 解析、
分维度评分、强弱候选人排序、面试一次一问、空答低分、完整模拟面试生成报告。

---

## 9. 智能体安全与边界

- AI 不做最终录用决定，只做辅助判断；结论标注「仅供 HR 辅助参考，最终由人工确认」。
- 必须输出证据，不允许只给结论；简历中无证据的能力不默认具备。
- 不依据性别、婚育、民族、宗教、健康等非岗位相关因素做负面判断。
- 年龄/学历/年限仅在 JD 明确要求时作为岗位匹配信息。
- 低置信度判断标记「需人工复核」；所有评分可解释、可追溯。

## 10. 后续接入飞书多维表格 / Coze / 企业微信

`.env` 与 `app/config.py` 已预留 `FEISHU_*` / `COZE_*` / `WECHAT_WORK_*`。
服务层统一通过 `llm.run(task, ...)` 与数据表交互，接入外部系统时只需新增
「sink/source 适配器」（如把 `applications` 评分写回飞书多维表格），核心流程不变。
设计思想详见 [docs/workflow_design.md](docs/workflow_design.md)。

## 11. 二次开发建议

- 按岗位复制 `data/scoring_rules.json` 并调权重；扩充 `app/mock_llm.py` 的技能/院校词库。
- 增加 JD-简历语义向量匹配，减少关键词漏判。
- 接入真实大模型后做 A/B 评测，校准与 Mock 的一致性。
- 把 Streamlit 演示前端替换为飞书小程序 / 企业微信侧边栏。

## 12. 写进作品集 / 简历 / 面试

**一句话定位**：从 0 到 1 设计并实现的「HR 简历筛选 + AI 面试」提效智能体，
覆盖产品设计、Agent 工作流编排、Python 全栈与工程落地。

**简历可量化写法**：
- 设计 7 维结构化评分模型（加权指标匹配），把「凭感觉初筛」变为带证据、可追溯的评估，
  单份初筛从 5-10 分钟降到 1-2 分钟。
- 用「任务拆分 + JSON 三重兜底」保证大模型输出稳健，离线/真实模型双模式可切换。
- 实现一次一问的 AI 模拟面试智能体，含逐轮打分与提升报告。

**面试可讲的亮点**：任务拆分为何提速提质、评分如何可解释、如何防止 AI 越权做录用决定、
如何为接入飞书/Coze 预留架构。详见 [docs/case_study.md](docs/case_study.md)。
