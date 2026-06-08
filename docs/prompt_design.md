# Prompt 设计

所有 prompt 位于 `app/prompts/*.md`，由 `app/prompts/__init__.py:load_prompt` 加载。
每个 prompt 统一包含：**角色 / 任务 / 输入 / 输出格式 / 约束**。

## 通用约束（安全红线）

- 不许编造：简历/JD 中没有的信息不得补全。
- 不确定就标记「无」或「需人工复核」。
- 必须输出 JSON 或 Markdown，且**只**输出结构化内容（不要 ```json 外壳、不要解释）。
- 不得依据性别、婚育、民族、宗教、健康等非岗位相关因素做负面判断。
- AI 不做最终录用决定，只做辅助。

## 7 个 prompt 一览

| 文件 | 用途 | 输出 |
| --- | --- | --- |
| `jd_parse_prompt.md` | JD → 结构化字段 | JSON |
| `resume_extract_prompt.md` | 简历 → 结构化信息 | JSON |
| `resume_score_prompt.md` | 逐维度打分 + 证据/风险 | JSON 数组 |
| `screening_decision_prompt.md` | 汇总筛选结论 | JSON |
| `interview_plan_prompt.md` | 面试官提纲 | JSON |
| `interview_agent_prompt.md` | AI 模拟面试，一次一问 | JSON |
| `interview_evaluate_prompt.md` | 单轮回答点评打分 | JSON |

## 4 个核心 prompt 的设计要点

### 1. resume_extract_prompt
- 强调缺失填「无」、不编造；手机号 + 邮箱都要提取；院校取最近一段；
  项目 `achievements` 优先抓带数字的量化结果；`raw_text` 原样保留以便证据回溯。

### 2. resume_score_prompt
- 「加权指标匹配」思路：命中越充分得分越高；**每个维度必须给证据与风险**；
  分数不超过该维度满分；学历/年限仅在 JD 明确要求时计权；无法判断给中性分 + 标记复核。

### 3. interview_plan_prompt
- 拒绝泛泛问题；每题对应 JD/简历证据；优先追问「看起来强但证据不足」之处；
  项目按背景-目标-角色-动作-难点-结果-复盘追问；每题给 1-3 层追问 + 评分指引；
  题量与时长匹配。

### 4. interview_agent_prompt
- **交互纪律**：一次只问一个问题，绝不一次性列出所有题；第一题考察岗位理解，
  逐步深入；不重复已问标题；语气像真实面试官。

## 经验教训（来自参考案例）

- 「给我所有文本」有效，「给我所有内容」会被模型理解成只给标题——
  **需要混合自然语言 + 明确约束**，必要时用代码语言描述。
- 一个节点只做一个任务；多任务会拖慢并降质。
- 用户提示词可留空，把关键变量编入系统提示词更可控（针对 Coze 的经验）。
- 模型可能篡改字段名（如把「参与项目身份」写成「项目参与身份」），
  因此输出后要用 Pydantic 校验 + 兜底。
