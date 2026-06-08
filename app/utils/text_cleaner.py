"""简历 / JD 文本清洗。"""
from __future__ import annotations

import re

_CJK = re.compile(r"[一-鿿]")


def _is_noise_line(line: str) -> bool:
    """识别 PDF 水印/Logo 被抽取出的碎片行。

    典型表现：去掉空格后只剩 1-2 个非中文字符（如 "Q Q"、"~ ~"、"Of"、"_ _"），
    这些行没有中文、没有有效信息，直接丢弃，避免污染简历证据与报告。
    """
    compact = line.replace(" ", "")
    if not compact:
        return False  # 空行交给后续合并逻辑
    if _CJK.search(compact):
        return False  # 含中文，保留
    if any(ch.isdigit() for ch in compact):
        return False  # 含数字（可能是电话/年份片段），保留
    return len(compact) <= 2


def clean_text(text: str) -> str:
    """归一化空白、去除不可见字符与水印碎片，保留段落结构。"""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("　", " ").replace("\xa0", " ")
    # 去掉控制字符（保留换行/制表）
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    # 丢弃水印碎片行
    lines = [ln for ln in text.split("\n") if not _is_noise_line(ln)]
    text = "\n".join(ln.rstrip() for ln in lines)
    # 合并 3 个以上连续空行为 2 个
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def truncate(text: str, max_chars: int = 8000) -> str:
    """限制送入大模型的文本长度，避免超长。"""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...(内容过长已截断)"
