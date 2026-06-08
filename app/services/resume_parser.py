"""简历解析服务：把上传的文件 / 粘贴文本统一转成清洗后的纯文本。"""
from __future__ import annotations

from pathlib import Path
from typing import Union

from app.utils.file_reader import read_bytes, read_file
from app.utils.text_cleaner import clean_text


def parse_resume_file(path: Union[str, Path]) -> str:
    """从磁盘文件读取简历纯文本。"""
    return read_file(path)


def parse_resume_bytes(data: bytes, file_name: str) -> str:
    """从上传字节流读取简历纯文本。"""
    return read_bytes(data, file_name)


def parse_resume_text(text: str) -> str:
    """直接粘贴的简历文本。"""
    return clean_text(text)
