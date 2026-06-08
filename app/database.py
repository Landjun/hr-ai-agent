"""数据库引擎、建表、会话与默认评分规则初始化。"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine, select

from app.config import settings
from app.models import ScoringRule  # noqa: F401  确保模型被注册
from app import models  # noqa: F401  注册所有表

# SQLite 需要 check_same_thread=False 以便 FastAPI / Streamlit 多线程访问
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def init_db() -> None:
    """建表 + 写入默认评分规则（幂等）。"""
    SQLModel.metadata.create_all(engine)
    _seed_default_scoring_rules()


def get_session() -> Iterator[Session]:
    """FastAPI 依赖注入用的会话生成器。"""
    with Session(engine) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    """服务层 / 脚本里用的上下文管理器。"""
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# 默认 7 维评分规则（总分 100），与 data/scoring_rules.json 保持一致
DEFAULT_DIMENSIONS = [
    ("通用", "岗位匹配度", "", 25.0, "候选人整体方向、求职意向与 JD 岗位的匹配程度"),
    ("通用", "必备技能匹配", "", 25.0, "JD must-have 硬技能在简历中的命中与证据强度"),
    ("通用", "项目经验匹配", "", 20.0, "项目背景/角色/难点/结果与岗位要求的契合度"),
    ("通用", "工作经历匹配", "", 15.0, "公司、岗位、年限、职责与 JD 的契合度"),
    ("通用", "教育背景", "", 5.0, "学历、院校、专业与岗位要求的匹配（仅 JD 明确要求时计权）"),
    ("通用", "稳定性与表达质量", "", 5.0, "跳槽频率、简历表达清晰度与逻辑性"),
    ("通用", "加分项", "", 5.0, "竞赛/开源/论文/证书/个人作品等额外亮点"),
]


def _seed_default_scoring_rules() -> None:
    with session_scope() as session:
        exists = session.exec(select(ScoringRule).limit(1)).first()
        if exists:
            return
        for job_title, dim, sub, max_score, desc in DEFAULT_DIMENSIONS:
            session.add(
                ScoringRule(
                    job_title=job_title,
                    dimension=dim,
                    sub_dimension=sub,
                    max_score=max_score,
                    weight=1.0,
                    description=desc,
                )
            )
