import json
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from google import genai
from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 35.0  # Seconds per HTTP interaction
FALLBACK_MODEL = "gemini-3.5-flash-lite"

_rate_lock = threading.Lock()
_last_call_timestamp = 0.0


def _rate_limit_pace(min_interval: float = 1.2):
    """Ensures at least min_interval seconds between consecutive Gemini calls across all threads."""
    global _last_call_timestamp
    with _rate_lock:
        now = time.time()
        elapsed = now - _last_call_timestamp
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _last_call_timestamp = time.time()


def _is_retryable_error(e: Exception) -> bool:
    err_str = str(e).lower()
    return (
        "429" in err_str
        or "500" in err_str
        or "502" in err_str
        or "503" in err_str
        or "504" in err_str
        or "quota" in err_str
        or "resourceexhausted" in err_str
        or "timeout" in err_str
        or "timed out" in err_str
        or "connection" in err_str
        or "remotedisconnected" in err_str
        or "reset" in err_str
    )


def _init_client() -> genai.Client:
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured in settings or environment.")
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    # Crucial: Disable Speakeasy's built-in retry loop which parses Retry-After (up to 24000s)
    # and causes process to hang indefinitely for hours on free tier 429s.
    if hasattr(client, "interactions") and hasattr(client.interactions, "sdk_configuration"):
        client.interactions.sdk_configuration.retry_config = None
    return client


def generate_text(
    system_instruction: str,
    prompt: str,
    thinking_level: str = "low",
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """
    Calls Gemini model via the Interactions API to generate plain text.
    Retries on 429, 5xx, and network timeouts with bounded backoff.
    Falls back to gemini-3.5-flash-lite if daily quota on primary model is exceeded.
    """
    client = _init_client()
    model = settings.GEMINI_MODEL

    attempts = 0
    backoff = 1.5

    while attempts < 3:
        try:
            _rate_limit_pace(1.2)
            it = client.interactions.create(
                model=model,
                system_instruction=system_instruction,
                input=prompt,
                generation_config={"thinking_level": thinking_level},
                timeout=timeout,
            )
            return it.output_text or ""
        except Exception as e:
            attempts += 1
            err_str = str(e).lower()
            if ("rate limit" in err_str or "quota" in err_str) and model != FALLBACK_MODEL:
                logger.warning(f"Quota exceeded for {model}. Falling back to {FALLBACK_MODEL}...")
                model = FALLBACK_MODEL
                continue
            if _is_retryable_error(e) and attempts < 3:
                logger.warning(
                    f"generate_text failed with {e}. Retrying in {backoff}s (attempt {attempts}/3)..."
                )
                time.sleep(backoff)
                backoff = min(backoff * 1.5, 4.0)
            else:
                raise e

    return ""


def run_agent(
    system_instruction: str,
    user_input: str,
    declarations: List[Dict[str, Any]],
    execute: Callable[[str, Dict[str, Any]], Tuple[Dict[str, Any], Any]],
    thinking_level: str = "low",
    max_rounds: int = 8,
    on_event: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Tuple[str, int]:
    """
    Runs an autonomous Gemini agent tool-calling loop using the Interactions API.
    - Loops up to max_rounds while function_calls are returned.
    - Executes all parallel function calls in a round and returns all results in one input list.
    - Re-sends tools and system_instruction every round.
    - Enforces rate-limiting pace and socket/HTTP timeout to prevent hangs.
    - Automatically falls back to FALLBACK_MODEL if primary model hits quota limit.
    - Emits on_event callbacks for tool.call and tool.result.
    - Returns (final_text, total_tool_calls).
    """
    client = _init_client()
    model = settings.GEMINI_MODEL

    total_tool_calls = 0
    previous_id = None
    next_input: Any = user_input

    def call_interactions_with_retry(**kwargs):
        nonlocal model
        attempts = 0
        backoff = 1.5
        kwargs["timeout"] = timeout
        while attempts < 3:
            try:
                _rate_limit_pace(1.2)
                return client.interactions.create(**kwargs)
            except Exception as e:
                attempts += 1
                err_str = str(e).lower()
                if ("rate limit" in err_str or "quota" in err_str) and kwargs.get("model") != FALLBACK_MODEL:
                    logger.warning(f"Quota exceeded for {kwargs.get('model')}. Falling back to {FALLBACK_MODEL}...")
                    model = FALLBACK_MODEL
                    kwargs["model"] = FALLBACK_MODEL
                    continue
                if _is_retryable_error(e) and attempts < 3:
                    logger.warning(f"Interactions API failed with {e}. Retrying in {backoff}s...")
                    time.sleep(backoff)
                    backoff = min(backoff * 1.5, 4.0)
                else:
                    raise e

    for round_idx in range(max_rounds):
        kwargs: Dict[str, Any] = {
            "model": model,
            "system_instruction": system_instruction,
            "input": next_input,
            "generation_config": {"thinking_level": thinking_level},
        }
        if declarations:
            kwargs["tools"] = declarations
        if previous_id:
            kwargs["previous_interaction_id"] = previous_id

        interaction = call_interactions_with_retry(**kwargs)
        previous_id = interaction.id

        # Inspect steps for function calls
        function_calls = []
        for step in interaction.steps or []:
            step_type = getattr(step, "type", "")
            if step_type == "function_call" or (hasattr(step, "name") and hasattr(step, "arguments")):
                function_calls.append(step)

        if not function_calls:
            # Model finished reasoning and returned final text
            return interaction.output_text or "", total_tool_calls

        # Execute all function calls
        function_results = []
        for fc in function_calls:
            total_tool_calls += 1
            fn_name = getattr(fc, "name", "")
            raw_args = getattr(fc, "arguments", {})
            call_id = getattr(fc, "id", f"call_{total_tool_calls}")

            args: Dict[str, Any] = raw_args if isinstance(raw_args, dict) else json.loads(raw_args or "{}")

            if on_event:
                on_event("tool.call", {"tool": fn_name, "args": args})

            # Execute tool
            llm_payload, tool_result = execute(fn_name, args)

            if on_event:
                on_event("tool.result", {"tool": fn_name, "payload": llm_payload, "result": tool_result})

            function_results.append({
                "type": "function_result",
                "name": fn_name,
                "call_id": call_id,
                "result": [{"type": "text", "text": json.dumps(llm_payload)}],
            })

        next_input = function_results

    # Hit max_rounds: force final response
    kwargs = {
        "model": model,
        "system_instruction": system_instruction,
        "input": "Conclude your findings and provide your final response now based on all evidence gathered.",
        "previous_interaction_id": previous_id,
        "generation_config": {"thinking_level": thinking_level},
    }
    final_it = call_interactions_with_retry(**kwargs)
    return final_it.output_text or "", total_tool_calls
