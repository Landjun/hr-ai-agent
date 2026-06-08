"""稳健的 JSON 解析。

参考案例的核心经验：大模型输出的 JSON 经常夹带 ```json 外壳、物理换行、
多余前后缀。这里实现「三重兜底」解析，最大限度抢救出结构化数据，
解析彻底失败也不让流水线崩溃。
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional


def _strip_code_fence(s: str) -> str:
    s = re.sub(r"```json", "", s, flags=re.IGNORECASE)
    s = s.replace("```", "")
    return s.strip()


def _extract_braced(s: str) -> Optional[str]:
    """截取第一个 { 或 [ 到与之配对的结尾，去掉前后的解释性文字。"""
    start = None
    for i, ch in enumerate(s):
        if ch in "{[":
            start = i
            opener = ch
            break
    if start is None:
        return None
    closer = "}" if opener == "{" else "]"
    depth = 0
    for j in range(start, len(s)):
        if s[j] == opener:
            depth += 1
        elif s[j] == closer:
            depth -= 1
            if depth == 0:
                return s[start:j + 1]
    return s[start:]  # 没闭合也先返回，交给后续兜底


def parse_json(raw: Any, default: Any = None) -> Any:
    """把大模型原始输出解析成 dict / list。失败返回 default。"""
    if raw is None:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    text = str(raw)

    # 尝试 1：原生解析
    try:
        return json.loads(text)
    except Exception:
        pass

    # 尝试 2：去掉 markdown 外壳后解析
    cleaned = _strip_code_fence(text)
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # 尝试 3：截取花括号片段
    braced = _extract_braced(cleaned)
    if braced:
        try:
            return json.loads(braced)
        except Exception:
            # 尝试 3.5：转义裸换行
            fixed = braced.replace("\n", "\\n").replace("\r", "\\r")
            try:
                return json.loads(fixed)
            except Exception:
                pass

    return default
