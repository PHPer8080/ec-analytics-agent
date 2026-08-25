"""Model Armor による入出力サニタイズプラグイン

before_model_callback で入力を、after_model_callback で応答を sanitize API に通し、
PII・インジェクション・RAI・悪意ある URI の一致をブロックする。
有効化は MODEL_ARMOR_TEMPLATE env var の有無で切り替える。
"""

import logging
import os

import google.auth
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins.base_plugin import BasePlugin
from google.auth.transport.requests import AuthorizedSession
from google.genai import types

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
DEFAULT_LOCATION = "us-central1"
MATCH_FOUND = "MATCH_FOUND"
BLOCKING_FILTERS = ("sdp", "pi_and_jailbreak", "rai", "malicious_uris", "csam")
# 初回はコールドスタートで 10 秒程度かかる (2 回目以降は 1 秒未満)
TIMEOUT_SECONDS = 30

BLOCKED_MESSAGE = "安全性チェックによりブロックされました。内容を変えて再度お試しください。"
UNAVAILABLE_MESSAGE = "安全性チェックを実行できなかったため、処理を中断しました。時間をおいて再度お試しください。"


def text_response(text: str) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))


def last_text(parts: list[types.Part] | None) -> str | None:
    return next((part.text for part in reversed(parts or []) if part.text), None)


class ModelArmorPlugin(BasePlugin):
    """Model Armor の sanitize API をモデル呼び出しの前後に適用する

    Args:
      template_id: Model Armor テンプレート ID
      project_id: 未指定なら GOOGLE_CLOUD_PROJECT → ADC の順で解決
      location: 未指定なら MODEL_ARMOR_LOCATION (既定 us-central1)
      fail_closed: sanitize API 失敗時にブロックするか
      name: プラグイン名
    """

    def __init__(
        self,
        *,
        template_id: str,
        project_id: str | None = None,
        location: str | None = None,
        fail_closed: bool = True,
        name: str = "model_armor",
    ) -> None:
        super().__init__(name=name)
        credentials, adc_project = google.auth.default(scopes=SCOPES)
        project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT") or adc_project
        if not project_id:
            raise ValueError("GCP project ID を解決できません。GOOGLE_CLOUD_PROJECT または ADC を確認してください")

        location = location or os.environ.get("MODEL_ARMOR_LOCATION", DEFAULT_LOCATION)
        self.session = AuthorizedSession(credentials)
        self.fail_closed = fail_closed
        self.url = (
            f"https://modelarmor.{location}.rep.googleapis.com/v1"
            f"/projects/{project_id}/locations/{location}/templates/{template_id}"
        )

    def check(self, method: str, key: str, text: str) -> LlmResponse | None:
        """テキストを検査する。一致があればブロック用の応答を返す。問題なければ None"""
        try:
            response = self.session.post(f"{self.url}:{method}", json={key: {"text": text}}, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
        except Exception:
            logger.exception("Model Armor %s の呼び出しに失敗しました", method)
            return text_response(UNAVAILABLE_MESSAGE) if self.fail_closed else None

        result = response.json().get("sanitizationResult", {})
        if result.get("filterMatchState") != MATCH_FOUND:
            return None
        filters = result.get("filterResults") or {}

        for name in BLOCKING_FILTERS:
            details = (filters.get(name) or {}).values()
            if any(isinstance(d, dict) and d.get("matchState") == MATCH_FOUND for d in details):
                logger.warning("Model Armor がブロックしました: filter=%s", name)
                return text_response(BLOCKED_MESSAGE)
        return None

    async def before_model_callback(
        self, *, callback_context: CallbackContext, llm_request: LlmRequest
    ) -> LlmResponse | None:
        contents = [content for content in (llm_request.contents or []) if content.role == "user"]
        text = last_text(contents[-1].parts if contents else None)
        return self.check("sanitizeUserPrompt", "userPromptData", text) if text else None

    async def after_model_callback(
        self, *, callback_context: CallbackContext, llm_response: LlmResponse
    ) -> LlmResponse | None:
        if llm_response.partial:
            return None
        text = last_text(llm_response.content.parts if llm_response.content else None)
        return self.check("sanitizeModelResponse", "modelResponseData", text) if text else None


def build_model_armor_plugin() -> ModelArmorPlugin | None:
    """MODEL_ARMOR_TEMPLATE が設定されていればプラグインを返す。未設定なら None"""
    template_id = os.environ.get("MODEL_ARMOR_TEMPLATE")
    if not template_id:
        logger.info("MODEL_ARMOR_TEMPLATE が未設定のため、Model Armor による検査は無効です")
        return None
    fail_closed = os.environ.get("MODEL_ARMOR_FAIL_CLOSED", "true").strip().lower() != "false"
    return ModelArmorPlugin(template_id=template_id, fail_closed=fail_closed)
