"""pytest 公共夹具：使用临时 SQLite，避免污染开发库。"""
import os
import tempfile

# 必须在 import app 之前设置环境变量，让 config 读到临时库
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ.setdefault("LLM_API_KEY", "")  # 强制离线 Mock，保证测试可离线跑

import pytest  # noqa: E402

from app.database import init_db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    init_db()
    yield
