# services/ai.py
#
# Thin wrapper around the LLM provider. Groq is the primary provider
# (OpenAI-compatible API); OpenAI works as a fallback when only
# OPENAI_API_KEY is set. All callers (views, tasks) stay the same.

from openai import OpenAI
from django.conf import settings

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"

# Client is created lazily so the server can boot without an API key —
# only AI endpoints fail (with a clear message) when the key is missing.
_client = None
_model = None

MAX_TOKENS = 1000


def _get_client() -> OpenAI:
    global _client, _model
    if _client is None:
        groq_key = getattr(settings, "GROQ_API_KEY", None)
        if groq_key:
            _client = OpenAI(api_key=groq_key, base_url=GROQ_BASE_URL)
            _model = getattr(settings, "AI_MODEL", None) or GROQ_DEFAULT_MODEL
        elif settings.OPENAI_API_KEY:
            _client = OpenAI(api_key=settings.OPENAI_API_KEY)
            _model = getattr(settings, "AI_MODEL", None) or OPENAI_DEFAULT_MODEL
        else:
            raise RuntimeError(
                "AI is not configured: set GROQ_API_KEY (preferred) or OPENAI_API_KEY."
            )
    return _client


def _get_model() -> str:
    _get_client()
    return _model


def complete(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = MAX_TOKENS,
) -> str:
    """
    Single-turn completion.
    Used for pitch generation, proposal generation, one-shot tasks.

    Args:
        system_prompt : Instructions for the AI (role, tone, format)
        user_prompt   : The actual task/data to process
        temperature   : 0.0 = deterministic, 1.0 = creative. 0.7 is good default.
        max_tokens    : Max response length

    Returns:
        AI response as plain string.

    Raises:
        RuntimeError if API call fails.
    """
    try:
        response = _get_client().chat.completions.create(
            model=_get_model(),
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"AI API error: {e}")


def chat(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = MAX_TOKENS,
) -> str:
    """
    Multi-turn conversation.
    Used for AI chat assistant where history is passed each time.

    Args:
        messages : Full conversation history in OpenAI format:
                   [
                     {'role': 'system',    'content': '...'},
                     {'role': 'user',      'content': '...'},
                     {'role': 'assistant', 'content': '...'},
                     {'role': 'user',      'content': '...'},
                   ]
        temperature : Creativity level
        max_tokens  : Max response length

    Returns:
        AI response as plain string.

    Raises:
        RuntimeError if API call fails.
    """
    try:
        response = _get_client().chat.completions.create(
            model=_get_model(),
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"AI API error: {e}")


def complete_json(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = MAX_TOKENS,
) -> str:
    """
    JSON mode completion.
    Requires the system prompt to explicitly instruct the model to return JSON.
    """
    try:
        response = _get_client().chat.completions.create(
            model=_get_model(),
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"AI API error: {e}")
