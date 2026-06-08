"""简历信息抽取服务：简历纯文本 → 结构化候选人信息。"""
from __future__ import annotations

from typing import Any, Dict

from app.llm_client import get_llm
from app.prompts import load_prompt
from app.schemas import ResumeStructured
from app.utils.json_parser import parse_json
from app.utils.text_cleaner import truncate


def extract_resume(raw_text: str) -> Dict[str, Any]:
    """抽取简历结构化信息，返回符合 ResumeStructured 的 dict。"""
    system = load_prompt("resume_extract_prompt")
    user = f"请从以下简历中提取结构化信息：\n\n{truncate(raw_text, 8000)}"

    raw = get_llm().run("resume_extract", system, user, payload={"raw_text": raw_text})
    data = parse_json(raw, default={})

    try:
        model = ResumeStructured(**data) if isinstance(data, dict) else ResumeStructured()
    except Exception:
        model = ResumeStructured(name="（解析失败，请人工复核）")

    # 始终保留原文，便于后续证据回溯
    if not model.raw_text:
        model.raw_text = raw_text
    return model.model_dump()
