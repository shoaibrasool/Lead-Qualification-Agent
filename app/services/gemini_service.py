from __future__ import annotations

import logging
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.config import get_settings

logger = logging.getLogger(__name__)


def _is_rate_limit_error(exc: BaseException) -> bool:
    error_str = str(exc).lower()
    return "429" in error_str or "rate limit" in error_str or "resource exhausted" in error_str


_model: Optional[ChatGoogleGenerativeAI] = None


def get_model() -> ChatGoogleGenerativeAI:
    global _model
    if _model is None:
        settings = get_settings()
        _model = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            api_key=settings.gemini_api_key.get_secret_value(),
            safety_settings={
                "HARM_CATEGORY_HARASSMENT": "BLOCK_ONLY_HIGH",
                "HARM_CATEGORY_HATE_SPEECH": "BLOCK_ONLY_HIGH",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_ONLY_HIGH",
                "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_ONLY_HIGH",
            },
        )
    return _model


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=30),
    retry=retry_if_exception(_is_rate_limit_error),
    retry_error_callback=lambda retry_state: None,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def _invoke_with_retry(model: ChatGoogleGenerativeAI, messages: list) -> Optional[str]:
    try:
        response = model.invoke(messages)
        return response.content
    except Exception as e:
        if _is_rate_limit_error(e):
            raise
        logger.error("Non-retryable Gemini error: %s", e)
        return None


FALLBACK_MESSAGE = (
    "I'm sorry, I'm having trouble connecting right now. "
    "Let me save what we've discussed and someone from our team will follow up."
)


def generate_response(messages: list, system_prompt: str = "") -> str:
    model = get_model()

    if system_prompt:
        from langchain_core.messages import SystemMessage

        full_messages = [SystemMessage(content=system_prompt)] + messages
    else:
        full_messages = messages

    result = _invoke_with_retry(model, full_messages)
    if result is None:
        logger.error("Gemini invocation failed after all retries")
        return FALLBACK_MESSAGE
    return result
