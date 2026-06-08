"""简历 / JD 文本清洗。"""
from __future__ import annotations

import re


def clean_text(text: str) -> str:
    """归一化空白、去除不可见字符，保留段落结构。"""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("　", " ").replace("\xa0", " ")
    # 去掉控制字符（保留换行/制表）
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    # 合并 3 个以上连续空行为 2 个
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 行尾空白
    text = "\n".join(ln.rstrip() for ln in text.split("\n"))
    return text.strip()


def truncate(text: str, max_chars: int = 8000) -> str:
    """限制送入大模型的文本长度，避免超长。"""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...(内容过长已截断)"
