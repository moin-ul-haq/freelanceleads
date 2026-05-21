# services/ai.py
#
# Thin wrapper around OpenAI API.
# When switching to Claude later — only this file changes.
# All callers (views, tasks) stay the same.

from openai import OpenAI
from django.conf import settings

# Single client instance — reused across all calls
_client = OpenAI(api_key=settings.OPENAI_API_KEY)

MODEL = "gpt-4o-mini"
MAX_TOKENS = 1000


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
        response = _client.chat.completions.create(
            model=MODEL,
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
        response = _client.chat.completions.create(
            model=MODEL,
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
        response = _client.chat.completions.create(
            model=MODEL,
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
