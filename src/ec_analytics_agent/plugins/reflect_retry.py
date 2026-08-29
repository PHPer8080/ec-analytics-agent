from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins import ReflectAndRetryModelPlugin
from google.genai import types

MAX_RETRIES = 3
NO_USABLE_PART = "NO_USABLE_PART"
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


class EmptyTurnRetryPlugin(ReflectAndRetryModelPlugin):
    # ADK が error_code を立てるのは after_model_callback より後 (base_llm_flow.py:1213) なので、親のリトライに乗せるには先に立てる必要がある
    async def after_model_callback(
        self, *, callback_context: CallbackContext, llm_response: LlmResponse
    ) -> LlmResponse | None:
        if not llm_response.error_code and has_no_usable_part(llm_response):
            llm_response.error_code = NO_USABLE_PART
            if llm_response.finish_reason is None:
                llm_response.finish_reason = types.FinishReason.OTHER
        return await super().after_model_callback(callback_context=callback_context, llm_response=llm_response)


def build_reflect_retry_plugin() -> EmptyTurnRetryPlugin:
    # 上限超過で例外にすると一時的な失敗が実行全体の中断になるため、最後の応答を返す側に倒す
    return EmptyTurnRetryPlugin(
        max_retries=MAX_RETRIES, throw_exception_if_retry_exceeded=False, on_model_errors=MODEL_ERRORS
    )
