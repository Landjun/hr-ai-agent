"""Prompt 加载器：从同目录 .md 文件读取提示词模板。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent


@lru_cache
def load_prompt(name: str) -> str:
    """按文件名（不含扩展名）加载 prompt。找不到返回空串。"""
    path = PROMPT_DIR / f"{name}.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")
