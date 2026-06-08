"""SQLModel 数据表定义。

数据库是整个系统的核心（参考案例的「多维表格即数据库」思想）。
列表 / 字典字段统一用 JSON 列存储，方便结构化沉淀候选人数据。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Column, Text
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now()


# ---------------------------------------------------------------------------
# 1. jobs —— 岗位 / JD 表
# ---------------------------------------------------------------------------
class Job(SQLModel, table=True):
    __tablename__ = "jobs"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_title: str = ""
    department: str = ""
    jd_text: str = Field(default="", sa_column=Column(Text))
    must_have_requirements: list = Field(default_factory=list, sa_column=Column(JSON))
    nice_to_have_requirements: list = Field(default_factory=list, sa_column=Column(JSON))
    responsibilities: list = Field(default_factory=list, sa_column=Column(JSON))
    hard_skills: list = Field(default_factory=list, sa_column=Column(JSON))
    soft_skills: list = Field(default_factory=list, sa_column=Column(JSON))
    keywords: list = Field(default_factory=list, sa_column=Column(JSON))
    experience_requirements: str = ""
    education_requirements: str = ""
    interview_focus: list = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# 2. resumes —— 简历表
# ---------------------------------------------------------------------------
class Resume(SQLModel, table=True):
    __tablename__ = "resumes"

    id: Optional[int] = Field(default=None, primary_key=True)
    candidate_name: str = ""
    raw_text: str = Field(default="", sa_column=Column(Text))
    structured_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    file_name: str = ""
    created_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# 3. applications —— 投递 / 筛选结论表（job × resume）
# ---------------------------------------------------------------------------
class Application(SQLModel, table=True):
    __tablename__ = "applications"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id")
    resume_id: int = Field(foreign_key="resumes.id")
    total_score: float = 0.0
    level: str = ""
    summary: str = Field(default="", sa_column=Column(Text))
    strengths: list = Field(default_factory=list, sa_column=Column(JSON))
    risks: list = Field(default_factory=list, sa_column=Column(JSON))
    missing_requirements: list = Field(default_factory=list, sa_column=Column(JSON))
    suggested_questions: list = Field(default_factory=list, sa_column=Column(JSON))
    manual_review_needed: bool = True
    status: str = "screened"  # screened / shortlisted / rejected / interviewed
    created_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# 4. scoring_rules —— 结构化评分规则表
#    （岗位 / 大类 / 小类 / 指标 / 权重，对应参考案例的 A/B/C/D 规则表）
# ---------------------------------------------------------------------------
class ScoringRule(SQLModel, table=True):
    __tablename__ = "scoring_rules"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_title: str = "通用"
    dimension: str = ""        # 大类，如「必备技能匹配」
    sub_dimension: str = ""    # 小类
    max_score: float = 0.0     # 该大类满分
    weight: float = 1.0
    description: str = Field(default="", sa_column=Column(Text))
    created_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# 5. screening_records —— 分维度评分明细（可追溯、可解释）
# ---------------------------------------------------------------------------
class ScreeningRecord(SQLModel, table=True):
    __tablename__ = "screening_records"

    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(foreign_key="applications.id")
    dimension: str = ""
    score: float = 0.0
    max_score: float = 0.0
    evidence: list = Field(default_factory=list, sa_column=Column(JSON))
    risk: list = Field(default_factory=list, sa_column=Column(JSON))
    reason: str = Field(default="", sa_column=Column(Text))
    created_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# 6. interview_sessions —— 面试会话（协助面试官 / AI 模拟面试）
# ---------------------------------------------------------------------------
class InterviewSession(SQLModel, table=True):
    __tablename__ = "interview_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: Optional[int] = Field(default=None, foreign_key="jobs.id")
    resume_id: Optional[int] = Field(default=None, foreign_key="resumes.id")
    application_id: Optional[int] = Field(default=None, foreign_key="applications.id")
    mode: str = "assist"          # assist（协助面试官） / mock（AI 模拟面试）
    interview_round: str = "初面"  # 初面 / 技术面 / 业务面 / 终面
    duration_minutes: int = 30
    status: str = "active"         # active / finished
    plan_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    final_score: Optional[float] = None
    final_report: str = Field(default="", sa_column=Column(Text))
    created_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# 7. interview_messages —— 面试逐轮对话 + 评分
# ---------------------------------------------------------------------------
class InterviewMessage(SQLModel, table=True):
    __tablename__ = "interview_messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="interview_sessions.id")
    role: str = ""              # interviewer / candidate / system
    content: str = Field(default="", sa_column=Column(Text))
    dimension: str = ""
    score: Optional[float] = None
    feedback: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_now)


ALL_MODELS: list[Any] = [
    Job,
    Resume,
    Application,
    ScoringRule,
    ScreeningRecord,
    InterviewSession,
    InterviewMessage,
]
