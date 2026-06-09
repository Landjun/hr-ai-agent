"""数据库引擎、建表、会话与默认评分规则初始化。"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine, select

from app import models  # noqa: F401  注册所有表
from app.config import ROOT_DIR, settings
from app.models import ScoringRule  # noqa: F401  确保模型被注册

# SQLite 需要 check_same_thread=False 以便 FastAPI / Streamlit 多线程访问
# check_same_thread=False 允许多线程访问；timeout 让并发写时等待锁而不是立刻报错
connect_args = (
    {"check_same_thread": False, "timeout": 30}
    if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def init_db() -> None:
    """建表 + 写入默认评分规则 + 岗位专属规则（幂等）。"""
    SQLModel.metadata.create_all(engine)
    _seed_default_scoring_rules()
    _seed_job_rulesets_from_files()


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
        exists = session.exec(
            select(ScoringRule).where(ScoringRule.job_title == "通用").limit(1)
        ).first()
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


def _seed_job_rulesets_from_files() -> None:
    """从 data/scoring_rules*.json 载入岗位专属规则（job_title != 通用），幂等。

    JSON 结构：{"job_title": "...", "dimensions": [{"dimension","max_score","description"}...]}
    放一个新的 scoring_rules_xxx.json 即可新增一个岗位的评分规则，无需改代码。
    """
    import json

    data_dir = ROOT_DIR / "data"
    if not data_dir.exists():
        return
    for path in sorted(data_dir.glob("scoring_rules*.json")):
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        job_title = (spec.get("job_title") or "").strip()
        dims = spec.get("dimensions") or []
        if not job_title or job_title == "通用" or not dims:
            continue
        with session_scope() as session:
            exists = session.exec(
                select(ScoringRule).where(ScoringRule.job_title == job_title).limit(1)
            ).first()
            if exists:
                continue
            for d in dims:
                session.add(ScoringRule(
                    job_title=job_title,
                    dimension=d.get("dimension", ""),
                    sub_dimension="",
                    max_score=float(d.get("max_score", 0) or 0),
                    weight=1.0,
                    description=d.get("description", ""),
                ))
