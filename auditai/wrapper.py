"""wrap_client() — drop-in proxy for Anthropic & OpenAI clients."""

from __future__ import annotations

import re
import functools
from typing import Any, Optional

from .logger import AuditLogger
from .risk import RiskClassifier

# Redact API keys, Bearer tokens, and secret-looking values before logging
_SECRET_PATTERNS = re.compile(
    r"(sk-[A-Za-z0-9\-_]{20,}|Bearer\s+[A-Za-z0-9\-._~+/]+|api[_-]?key['\"]?\s*[:=]\s*['\"]?[A-Za-z0-9\-_]{16,})",
    re.IGNORECASE,
)

def _sanitize(text: str) -> str:
    return _SECRET_PATTERNS.sub("[REDACTED]", text)


def wrap_client(
    client: Any,
    project: str,
    log_dir: Optional[str] = None,
    risk_context: Optional[dict] = None,
    hitl_callback: Optional[callable] = None,
) -> Any:
    """Return a wrapped client that auto-logs every AI call.

    Args:
        client: An anthropic.Anthropic() or openai.OpenAI() instance.
        project: Your project name (used as log file prefix).
        log_dir: Override default log directory (~/.auditai/logs/).
        risk_context: Pre-computed risk assessment dict to tag calls.
        hitl_callback: Optional callable(call_id, entry) for HITL events.

    Returns:
        Wrapped client with identical API — drop-in replacement.

    Example:
        import anthropic
        from auditai import wrap_client

        client = wrap_client(anthropic.Anthropic(), project="my-app")
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Hello"}],
        )
    """
    logger = AuditLogger(project=project, log_dir=log_dir)
    classifier = RiskClassifier()

    client_type = _detect_client_type(client)

    if client_type == "anthropic":
        return _wrap_anthropic(client, logger, classifier, risk_context, hitl_callback)
    elif client_type == "openai":
        return _wrap_openai(client, logger, classifier, risk_context, hitl_callback)
    else:
        raise ValueError(
            f"Unsupported client type: {type(client).__name__}. "
            "Supported: anthropic.Anthropic, openai.OpenAI"
        )


def _detect_client_type(client: Any) -> str:
    module = type(client).__module__ or ""
    name = type(client).__name__ or ""
    if "anthropic" in module or name == "Anthropic":
        return "anthropic"
    if "openai" in module or name in ("OpenAI", "AzureOpenAI"):
        return "openai"
    # Fallback: inspect for known attributes
    if hasattr(client, "messages") and hasattr(client.messages, "create"):
        return "anthropic"
    if hasattr(client, "chat") and hasattr(client.chat, "completions"):
        return "openai"
    return "unknown"


# ── Anthropic wrapper ─────────────────────────────────────────────────────────

class _AnthropicMessagesProxy:
    def __init__(self, original_messages, logger, classifier, risk_context, hitl_callback):
        self._orig = original_messages
        self._logger = logger
        self._classifier = classifier
        self._risk_context = risk_context or {}
        self._hitl_cb = hitl_callback

    def create(self, *args, **kwargs) -> Any:
        messages = kwargs.get("messages", [])
        model = kwargs.get("model", "unknown")
        response = self._orig.create(*args, **kwargs)
        output_text = ""
        input_tokens = 0
        output_tokens = 0
        try:
            if hasattr(response, "content") and response.content:
                for block in response.content:
                    if hasattr(block, "text"):
                        output_text += block.text
            if hasattr(response, "usage"):
                input_tokens = getattr(response.usage, "input_tokens", 0)
                output_tokens = getattr(response.usage, "output_tokens", 0)
        except Exception:
            pass

        risk_cat = self._classifier.classify_call(
            model=model,
            input_messages=messages,
            output_text=output_text,
            context=self._risk_context,
        )
        hitl_required = self._risk_context.get("hitl_required", risk_cat in ("high", "unacceptable"))

        call_id = self._logger.log_call(
            model=model,
            provider="anthropic",
            input_messages=messages,
            output_text=output_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            risk_category=str(risk_cat),
            hitl_required=hitl_required,
            metadata={"args": _sanitize(str(args)[:200]) if args else ""},
        )

        if hitl_required and self._hitl_cb:
            self._hitl_cb(call_id, {"model": model, "risk_category": str(risk_cat)})

        return response

    # Proxy all other attribute access to the original messages object
    def __getattr__(self, name):
        return getattr(self._orig, name)


class _AnthropicClientProxy:
    def __init__(self, client, logger, classifier, risk_context, hitl_callback):
        self._client = client
        self.messages = _AnthropicMessagesProxy(
            client.messages, logger, classifier, risk_context, hitl_callback
        )

    def __getattr__(self, name):
        return getattr(self._client, name)


def _wrap_anthropic(client, logger, classifier, risk_context, hitl_callback):
    return _AnthropicClientProxy(client, logger, classifier, risk_context, hitl_callback)


# ── OpenAI wrapper ────────────────────────────────────────────────────────────

class _OpenAICompletionsProxy:
    def __init__(self, original_completions, logger, classifier, risk_context, hitl_callback):
        self._orig = original_completions
        self._logger = logger
        self._classifier = classifier
        self._risk_context = risk_context or {}
        self._hitl_cb = hitl_callback

    def create(self, *args, **kwargs) -> Any:
        messages = kwargs.get("messages", [])
        model = kwargs.get("model", "unknown")
        response = self._orig.create(*args, **kwargs)
        output_text = ""
        input_tokens = 0
        output_tokens = 0
        try:
            if hasattr(response, "choices") and response.choices:
                output_text = response.choices[0].message.content or ""
            if hasattr(response, "usage"):
                input_tokens = getattr(response.usage, "prompt_tokens", 0)
                output_tokens = getattr(response.usage, "completion_tokens", 0)
        except Exception:
            pass

        risk_cat = self._classifier.classify_call(
            model=model,
            input_messages=messages,
            output_text=output_text,
            context=self._risk_context,
        )
        hitl_required = self._risk_context.get("hitl_required", risk_cat in ("high", "unacceptable"))

        call_id = self._logger.log_call(
            model=model,
            provider="openai",
            input_messages=messages,
            output_text=output_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            risk_category=str(risk_cat),
            hitl_required=hitl_required,
        )

        if hitl_required and self._hitl_cb:
            self._hitl_cb(call_id, {"model": model, "risk_category": str(risk_cat)})

        return response

    def __getattr__(self, name):
        return getattr(self._orig, name)


class _OpenAIChatProxy:
    def __init__(self, original_chat, logger, classifier, risk_context, hitl_callback):
        self._chat = original_chat
        self.completions = _OpenAICompletionsProxy(
            original_chat.completions, logger, classifier, risk_context, hitl_callback
        )

    def __getattr__(self, name):
        return getattr(self._chat, name)


class _OpenAIClientProxy:
    def __init__(self, client, logger, classifier, risk_context, hitl_callback):
        self._client = client
        self.chat = _OpenAIChatProxy(
            client.chat, logger, classifier, risk_context, hitl_callback
        )

    def __getattr__(self, name):
        return getattr(self._client, name)


def _wrap_openai(client, logger, classifier, risk_context, hitl_callback):
    return _OpenAIClientProxy(client, logger, classifier, risk_context, hitl_callback)
