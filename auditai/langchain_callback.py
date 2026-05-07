"""LangChain callback handler — drop-in EU AI Act audit for any LangChain LLM/chain."""

from typing import Any, Optional
from uuid import UUID

from .logger import AuditLogger
from .risk import RiskClassifier


class AuditAICallbackHandler:
    """LangChain callback that logs every LLM call to the AuditAI audit trail.

    Usage::

        from langchain_anthropic import ChatAnthropic
        from auditai.langchain_callback import AuditAICallbackHandler

        handler = AuditAICallbackHandler(project="my-app")
        llm = ChatAnthropic(model="claude-sonnet-4-6", callbacks=[handler])
        llm.invoke("Hello")
    """

    def __init__(self, project: str, log_dir: Optional[str] = None):
        self._logger = AuditLogger(project=project, log_dir=log_dir)
        self._classifier = RiskClassifier()
        self._pending: dict[str, dict] = {}  # run_id → {model, messages}

    # ── LangChain callback protocol ─────────────────────────────────────────

    def on_llm_start(
        self,
        serialized: dict,
        prompts: list[str],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        model = (serialized.get("kwargs") or {}).get("model_name", "unknown")
        self._pending[str(run_id)] = {
            "model": model,
            "messages": [{"role": "user", "content": p} for p in prompts],
        }

    def on_chat_model_start(
        self,
        serialized: dict,
        messages: list,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        model = (serialized.get("kwargs") or {}).get("model_name", "unknown")
        flat = []
        for batch in messages:
            for m in batch:
                role = getattr(m, "type", "user")
                content = getattr(m, "content", str(m))
                flat.append({"role": role, "content": content})
        self._pending[str(run_id)] = {"model": model, "messages": flat}

    def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
        key = str(run_id)
        pending = self._pending.pop(key, {})
        model = pending.get("model", "unknown")
        messages = pending.get("messages", [])

        output_text = ""
        input_tokens = 0
        output_tokens = 0
        try:
            gen = response.generations[0][0]
            output_text = getattr(gen, "text", "") or ""
            usage = (response.llm_output or {}).get("usage", {})
            input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
            output_tokens = usage.get("output_tokens") or usage.get("completion_tokens") or 0
        except Exception:
            pass

        risk_cat = self._classifier.classify_call(
            model=model, input_messages=messages, output_text=output_text
        )
        self._logger.log_call(
            model=model,
            provider="langchain",
            input_messages=messages,
            output_text=output_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            risk_category=str(risk_cat),
            hitl_required=risk_cat in ("high", "unacceptable"),
            metadata={"run_id": key},
        )

    def on_llm_error(self, error: Exception, *, run_id: UUID, **kwargs: Any) -> None:
        self._pending.pop(str(run_id), None)

    # Make it work as both a list item and a Callbacks object
    def __iter__(self):
        yield self
