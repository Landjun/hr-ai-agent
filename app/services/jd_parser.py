"""JD 解析服务：JD 原文 → 结构化字段。"""
from __future__ import annotations

from typing import Any, Dict

from app.llm_client import get_llm
from app.prompts import load_prompt
from app.schemas import JDStructured
from app.utils.json_parser import parse_json
from app.utils.text_cleaner import clean_text, truncate


def parse_jd(jd_text: str) -> Dict[str, Any]:
    """解析 JD，返回符合 JDStructured 的 dict。"""
    jd_text = clean_text(jd_text)
    system = load_prompt("jd_parse_prompt")
    user = f"请解析以下 JD：\n\n{truncate(jd_text, 6000)}"

    raw = get_llm().run("jd_parse", system, user, payload={"jd_text": jd_text})
    data = parse_json(raw, default={})

    # 用 Pydantic 校验 + 补全缺省字段
    try:
        model = JDStructured(**data) if isinstance(data, dict) else JDStructured()
    except Exception:
        model = JDStructured(job_title="（解析失败，请人工补充）")
    return model.model_dump()
