import logging

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins import ReflectAndRetryModelPlugin
from google.genai import types

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
NO_USABLE_PART = "NO_USABLE_PART"
FALLBACK_TEXT = "応答を生成できませんでした。お手数ですが、もう一度お試しください。"
BLOCKED_TEXT = "安全性の判定により応答を生成できませんでした。内容を変えてお試しください。"
# フィルタでブロックされた応答はリトライしても同じ結果になる
BLOCKED_FINISH_REASONS = frozenset(
    {
        types.FinishReason.SAFETY,
        types.FinishReason.BLOCKLIST,
        types.FinishReason.PROHIBITED_CONTENT,
        types.FinishReason.SPII,
    }
)
# 親は error_code が立っている応答しか見ないので、STOP / OTHER を足しても正常応答は素通りする
MODEL_ERRORS = [
    types.FinishReason.MALFORMED_FUNCTION_CALL,
    types.FinishReason.STOP,
    types.FinishReason.OTHER,
]


def has_no_usable_part(llm_response: LlmResponse) -> bool:
    if llm_response.partial or llm_response.interrupted:
        return False
    parts = llm_response.content.parts if llm_response.content else None
    return not any(
        part.text or part.function_call or part.function_response or part.inline_data or part.executable_code
        for part in (parts or [])
    )


def fallback_response(text: str) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))


class EmptyTurnRetryPlugin(ReflectAndRetryModelPlugin):
    # ADK が error_code を立てるのは after_model_callback より後 (base_llm_flow.py:1213)。
    # 親のリトライに乗せるには先に立てる必要がある
    async def after_model_callback(
        self, *, callback_context: CallbackContext, llm_response: LlmResponse
    ) -> LlmResponse | None:
        if not llm_response.error_code and has_no_usable_part(llm_response):
            if llm_response.finish_reason in BLOCKED_FINISH_REASONS:
                logger.warning("フィルタでブロックされました (%s)。定型文を返します", llm_response.finish_reason)
                return fallback_response(BLOCKED_TEXT)
            llm_response.error_code = NO_USABLE_PART
            if llm_response.finish_reason is None:
                llm_response.finish_reason = types.FinishReason.OTHER

        retried = await super().after_model_callback(callback_context=callback_context, llm_response=llm_response)
        # リトライ上限を超えると親は空応答をそのまま返す。無言でターンを終えない
        if has_no_usable_part(retried if retried is not None else llm_response):
            logger.warning("リトライ %d 回で復帰できませんでした。定型文を返します", MAX_RETRIES)
            return fallback_response(FALLBACK_TEXT)
        return retried


def build_reflect_retry_plugin() -> EmptyTurnRetryPlugin:
    # 上限超過で例外にすると一時的な失敗が実行全体の中断になるため、定型文を返す側に倒す
    return EmptyTurnRetryPlugin(
        max_retries=MAX_RETRIES, throw_exception_if_retry_exceeded=False, on_model_errors=MODEL_ERRORS
    )
