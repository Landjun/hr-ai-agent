# 数据表设计

数据库是系统核心。采用 SQLite + SQLModel，列表/字典字段以 JSON 列存储。
7 张表对应参考案例中的「多维表格」，并新增面试相关两张表。

## 1. jobs（岗位 / JD）
| 字段 | 说明 |
| --- | --- |
| id | 主键 |
| job_title / department | 岗位名 / 部门 |
| jd_text | JD 原文 |
| must_have_requirements / nice_to_have_requirements | 必备 / 加分要求（JSON 数组） |
| responsibilities / hard_skills / soft_skills / keywords | 职责 / 软硬技能 / 关键词（JSON） |
| experience_requirements / education_requirements | 年限 / 学历要求 |
| interview_focus | 面试重点（JSON） |
| created_at | 创建时间 |

## 2. resumes（简历）
| 字段 | 说明 |
| --- | --- |
| id | 主键 |
| candidate_name | 候选人姓名 |
| raw_text | 简历原文 |
| structured_json | 结构化简历（JSON） |
| file_name | 来源文件名 |
| created_at | 创建时间 |

## 3. applications（投递 / 筛选结论，job × resume）
| 字段 | 说明 |
| --- | --- |
| id | 主键 |
| job_id / resume_id | 外键 |
| total_score / level | 总分 / 推荐等级 |
| summary | 一句话结论 |
| strengths / risks / missing_requirements / suggested_questions | JSON 数组 |
| manual_review_needed | 是否需人工复核 |
| status | screened / shortlisted / rejected / interviewed |
| created_at | 创建时间 |

## 4. scoring_rules（结构化评分规则，对应参考案例 A/B/C/D 规则表）
| 字段 | 说明 |
| --- | --- |
| id | 主键 |
| job_title | 岗位（通用 / 具体岗位） |
| dimension / sub_dimension | 大类 / 小类 |
| max_score / weight | 满分 / 权重 |
| description | 说明 |
| created_at | 创建时间 |

## 5. screening_records（分维度评分明细，可追溯）
| 字段 | 说明 |
| --- | --- |
| id | 主键 |
| application_id | 外键 |
| dimension | 维度 |
| score / max_score | 得分 / 满分 |
| evidence / risk | 证据 / 风险（JSON 数组） |
| reason | 评分理由 |
| created_at | 创建时间 |

## 6. interview_sessions（面试会话）
| 字段 | 说明 |
| --- | --- |
| id | 主键 |
| job_id / resume_id / application_id | 外键（复用第一版数据） |
| mode | assist（协助面试官） / mock（AI 模拟面试） |
| interview_round / duration_minutes | 轮次 / 时长 |
| status | active / finished |
| plan_json | 面试提纲 / 模拟面试状态（JSON） |
| final_score / final_report | 最终分 / 最终报告 |
| created_at | 创建时间 |

## 7. interview_messages（逐轮问答 + 评分）
| 字段 | 说明 |
| --- | --- |
| id | 主键 |
| session_id | 外键 |
| role | interviewer / candidate / system |
| content | 内容 |
| dimension | 考察维度 |
| score | 单题得分（0-10） |
| feedback | 反馈（JSON：亮点/不足/追问/题目标题） |
| created_at | 创建时间 |

## 表间关系

```
jobs 1───* applications *───1 resumes
applications 1───* screening_records
jobs/resumes/applications ──* interview_sessions 1───* interview_messages
scoring_rules ── 评分时按 job_title 读取（通用回退）
```
