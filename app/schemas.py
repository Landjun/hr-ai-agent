"""Pydantic 结构化输出契约。

大模型的输出先用这些 schema 校验，校验失败再走兜底，保证写库数据干净。
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# ============================ JD ============================
class JDStructured(BaseModel):
    job_title: str = ""
    department: str = ""
    must_have_requirements: List[str] = Field(default_factory=list)
    nice_to_have_requirements: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    hard_skills: List[str] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list)
    experience_requirements: str = ""
    education_requirements: str = ""
    keywords: List[str] = Field(default_factory=list)
    interview_focus: List[str] = Field(default_factory=list)


# ========================== 简历 ============================
class WorkExperience(BaseModel):
    company: str = ""
    position: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""


class ProjectExperience(BaseModel):
    project_name: str = ""
    role: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""
    tech_stack: List[str] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)


class ResumeStructured(BaseModel):
    name: str = ""
    gender: str = ""
    age: str = ""
    phone: str = ""
    email: str = ""
    highest_education: str = ""
    school: str = ""
    major: str = ""
    years_of_experience: str = ""
    expected_position: str = ""
    expected_salary: str = ""
    expected_city: str = ""
    skills: List[str] = Field(default_factory=list)
    work_experiences: List[WorkExperience] = Field(default_factory=list)
    project_experiences: List[ProjectExperience] = Field(default_factory=list)
    self_evaluation: str = ""
    raw_text: str = ""


# ========================== 评分 ============================
class DimensionScore(BaseModel):
    dimension: str = ""
    score: float = 0.0
    max_score: float = 0.0
    evidence: List[str] = Field(default_factory=list)
    risk: List[str] = Field(default_factory=list)
    reason: str = ""


class ScreeningResult(BaseModel):
    total_score: float = 0.0
    level: str = ""
    summary: str = ""
    strengths: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    missing_requirements: List[str] = Field(default_factory=list)
    suggested_interview_questions: List[str] = Field(default_factory=list)
    manual_review_needed: bool = True
    dimension_scores: List[DimensionScore] = Field(default_factory=list)


# ===================== 面试官提纲（模式 A）=====================
class InterviewQuestion(BaseModel):
    question: str = ""
    dimension: str = ""
    why_ask: str = ""
    good_answer_signals: List[str] = Field(default_factory=list)
    bad_answer_signals: List[str] = Field(default_factory=list)
    follow_up_questions: List[str] = Field(default_factory=list)
    score_guide: str = ""


class InterviewPlan(BaseModel):
    interview_goal: str = ""
    interview_structure: List[str] = Field(default_factory=list)
    question_list: List[InterviewQuestion] = Field(default_factory=list)
    risk_verification_questions: List[str] = Field(default_factory=list)
    project_deep_dive_questions: List[str] = Field(default_factory=list)
    final_decision_rubric: List[str] = Field(default_factory=list)


# ===================== AI 模拟面试（模式 B）=====================
class MockQuestion(BaseModel):
    index: int = 1
    title: str = ""
    question: str = ""
    dimension: str = ""


class AnswerFeedback(BaseModel):
    score: float = 0.0          # 0-10
    highlights: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    follow_up: str = ""
    move_on: bool = False       # True = 进入下一题；False = 需要追问


# ===================== API 请求体 =====================
class JDCreateRequest(BaseModel):
    jd_text: str


class ResumeTextRequest(BaseModel):
    text: str
    file_name: str = "pasted.txt"


class ScoreRequest(BaseModel):
    job_id: int
    resume_id: int


class PlanRequest(BaseModel):
    job_id: int
    resume_id: Optional[int] = None
    application_id: Optional[int] = None
    interview_round: str = "初面"
    duration_minutes: int = 30


class MockStartRequest(BaseModel):
    jd_text: Optional[str] = None
    job_id: Optional[int] = None
    resume_text: Optional[str] = None
    interview_round: str = "技术面"
    duration_minutes: int = 30


class MockAnswerRequest(BaseModel):
    session_id: int
    answer: str
