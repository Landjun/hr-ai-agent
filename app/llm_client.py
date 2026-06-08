"""统一的大模型客户端。

设计要点：
1. OpenAI 兼容：通过 base_url + model 适配 DeepSeek / OpenAI / 通义千问 等。
2. 离线 Mock：未配置 API Key 时，自动调用内置启发式 Mock（app/mock_llm.py），
   让整条流水线在零配置下也能跑通、可演示。
3. 服务层统一调用 ``run(task, system, user, payload)``：
   - 真实模式：把 system/user 发给大模型，返回原始文本；
   - 离线模式：按 task 路由到 Mock，用 payload 生成结构化结果。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.config import settings
from app import mock_llm


class LLMClient:
    def __init__(self) -> None:
        self.offline = settings.offline_mode
        self._client = None
        self.last_error: Optional[str] = None  # 最近一次真实调用失败信息（供 UI 提示）
        if not self.offline:
            try:
                from openai import OpenAI

                self._client = OpenAI(
                    api_key=settings.llm_api_key,
                    base_url=settings.llm_base_url,
                    timeout=settings.llm_timeout,
                )
            except Exception as exc:  # 初始化失败也降级到离线，保证不崩
                print(f"[LLMClient] 初始化真实客户端失败，降级离线 Mock：{exc}")
                self.offline = True

    @property
    def mode(self) -> str:
        return "offline-mock" if self.offline else f"{settings.llm_provider}:{settings.llm_model}"

    def run(
        self,
        task: str,
        system: str,
        user: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> str:
        """执行一次大模型任务，返回原始文本（通常是 JSON 字符串）。

        task: 任务标识，离线模式据此路由 Mock。
        payload: 结构化输入，离线 Mock 用它生成可信结果。
        """
        payload = payload or {}
        if self.offline:
            return mock_llm.generate(task, payload)
        try:
            return self._chat(system, user)
        except Exception as exc:
            # 真实大模型调用失败（余额不足 402 / 超时 / 网络等）：
            # 不让异常冒泡崩溃页面，本次自动降级为离线 Mock，保证流程跑完。
            self.last_error = f"{type(exc).__name__}: {exc}"
            print(f"[LLMClient] 真实大模型调用失败，本次降级离线 Mock：{self.last_error}")
            return mock_llm.generate(task, payload)

    def _chat(self, system: str, user: str) -> str:
        assert self._client is not None
        resp = self._client.chat.completions.create(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""

    def chat_freeform(self, system: str, user: str, task: str = "freeform",
                      payload: Optional[Dict[str, Any]] = None) -> str:
        """自由文本对话（如 AI 面试官的口语化提问）。离线模式同样走 Mock。"""
        return self.run(task, system, user, payload)


# 全局单例
_llm: Optional[LLMClient] = None


def get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm
