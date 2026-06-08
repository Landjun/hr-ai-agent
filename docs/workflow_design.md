# 工作流设计

## 设计原则（来自参考案例的实战经验）

1. **任务拆分**：不要让一个大模型节点同时干多件事。单一职责跑得最快、最稳、最准。
2. **数据库是核心**：所有自动化都建立在结构化数据表之上。
3. **必须给证据**：每个判断都要能回溯到简历/JD 中的原文。
4. **稳健兜底**：大模型输出的 JSON 经常夹带 ```json 外壳、裸换行；用三重解析兜底，
   解析失败也不让流水线崩。
5. **可解释、可追溯**：评分过程与依据全部落库。

## 第一版：简历筛选流水线

| 步骤 | 服务 | 输入 | 输出 | 落库 |
| --- | --- | --- | --- | --- |
| 1. JD 解析 | `jd_parser.parse_jd` | JD 文本 | 结构化 JD | `jobs` |
| 2. 简历读取 | `resume_parser` | 文件/文本 | 纯文本 | — |
| 3. 简历抽取 | `resume_extractor.extract_resume` | 纯文本 | 结构化简历 | `resumes` |
| 4. 分维度评分 | `resume_scorer.score_resume` | JD+简历+规则 | 维度得分[] | — |
| 5. 筛选结论 | `screening_agent.screen` | 维度得分 | 总分/等级/结论 | `applications` + `screening_records` |
| 6. 排序 | `screening_agent.rank_for_job` | job_id | 排序表 | — |
| 7. 报告 | `report_generator` | application_id | Markdown/Excel/JSON | `outputs/` |

> 总分与等级在**本地**由维度分求和与阈值计算（不完全依赖大模型），保证与维度明细一致、可追溯。

## 第二版：面试流水线

### 模式 A 协助面试官
`interview_planner.generate_plan(job, resume, application, round, duration)`
→ 复用 JD/简历/评分报告 → 生成结构化提纲 → 落 `interview_sessions(mode='assist')`。

### 模式 B AI 模拟面试（一次一问）

```
start_mock ─▶ ask_next(第1题) ─┐
                               ▼
        ┌────────── submit_answer(回答) ──▶ 即时点评打分(evaluate_answer)
        │                 │
        │       should_finish? ── 否 ──▶ ask_next(下一题) ─┐
        │                 │ 是                              │
        │                 ▼                                 │
        └──────────── finish_mock ──▶ 生成最终报告           │
                                                            └──(循环)
```

- 题量由时长决定：15→3，30→4，45→5，60→6。
- 状态保存在 `interview_sessions.plan_json`（JD/简历/已问标题/最大题数）
  与 `interview_messages`（逐轮问答 + 分数 + 反馈）。

## 离线 Mock vs 真实大模型

- 未配置 `LLM_API_KEY` → `app/mock_llm.py` 用关键词匹配 + 规则启发式产出结构化结果，
  整条流水线零配置可跑、可演示。
- 配置 Key → `app/llm_client.py` 走 OpenAI 兼容接口（DeepSeek/通义/OpenAI 等）。
- 服务层对二者**无感知**：统一调用 `llm.run(task, system, user, payload)`。

## 后续集成预留

`.env` 已预留 `FEISHU_*` / `COZE_*` / `WECHAT_WORK_*`。后续可把
「评分结论写回飞书多维表格」「用 Coze 工作流并行抽取」等作为新的 sink/source 接入，
服务层接口保持不变。
