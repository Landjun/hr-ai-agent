"""集中式配置。

所有可调参数从环境变量 / .env 读取，禁止把 API Key 写死在代码里。
不配置 LLM_API_KEY 时 ``offline_mode`` 为 True，系统走离线 Mock，
保证零配置也能完整跑通整条流水线。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（本文件位于 <root>/app/config.py）
ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """从 .env / 环境变量加载的全局配置。"""

    # ---- 大模型 ----
    llm_provider: str = "deepseek"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    llm_temperature: float = 0.2
    llm_timeout: int = 60

    # ---- 存储 ----
    database_url: str = f"sqlite:///{(ROOT_DIR / 'hr_agent.db').as_posix()}"
    output_dir: str = str(ROOT_DIR / "outputs")

    # ---- 后续集成预留 ----
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_bitable_app_token: str = ""
    coze_api_token: str = ""
    coze_workflow_id: str = ""
    wechat_work_webhook: str = ""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def offline_mode(self) -> bool:
        """没有配置真实 API Key 时为 True，走内置 Mock 大模型。"""
        return not self.llm_api_key.strip()

    @property
    def screening_report_dir(self) -> Path:
        p = Path(self.output_dir) / "screening_reports"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def interview_report_dir(self) -> Path:
        p = Path(self.output_dir) / "interview_reports"
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    """单例配置，避免重复读取 .env。"""
    return Settings()


settings = get_settings()
