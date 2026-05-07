"""JSONL audit logger — append-only, never truncates."""

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    import fcntl as _fcntl
    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False  # Windows fallback


class AuditLogger:
    def __init__(self, project: str, log_dir: Optional[str] = None):
        self.project = project
        base = Path(log_dir) if log_dir else Path.home() / ".auditai" / "logs"
        base.mkdir(parents=True, exist_ok=True)
        self.log_path = base / f"{project}.jsonl"

    def log_call(
        self,
        *,
        model: str,
        provider: str,
        input_messages: list,
        output_text: str,
        input_tokens: int,
        output_tokens: int,
        risk_category: str = "low",
        hitl_required: bool = False,
        human_reviewed: Optional[bool] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        call_id = str(uuid.uuid4())
        input_str = json.dumps(input_messages, ensure_ascii=False)
        entry = {
            "call_id": call_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "project": self.project,
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "input_hash": hashlib.sha256(input_str.encode()).hexdigest(),
            "output_preview": output_text[:100] if output_text else "",
            "risk_category": risk_category,
            "hitl_required": hitl_required,
            "human_reviewed": human_reviewed,
            "metadata": metadata or {},
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            if _HAS_FCNTL:
                _fcntl.flock(f, _fcntl.LOCK_EX)
            try:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                f.flush()
            finally:
                if _HAS_FCNTL:
                    _fcntl.flock(f, _fcntl.LOCK_UN)
        return call_id

    def read_all(self) -> list[dict]:
        if not self.log_path.exists():
            return []
        entries = []
        with open(self.log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries

    def stats(self) -> dict:
        entries = self.read_all()
        if not entries:
            return {
                "total_calls": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "risk_breakdown": {},
                "hitl_events": 0,
                "models_used": [],
            }
        risk_breakdown: dict[str, int] = {}
        models: set[str] = set()
        hitl = 0
        in_tok = 0
        out_tok = 0
        for e in entries:
            risk_breakdown[e.get("risk_category", "unknown")] = (
                risk_breakdown.get(e.get("risk_category", "unknown"), 0) + 1
            )
            if e.get("hitl_required"):
                hitl += 1
            in_tok += e.get("input_tokens", 0)
            out_tok += e.get("output_tokens", 0)
            models.add(e.get("model", "unknown"))
        return {
            "total_calls": len(entries),
            "total_input_tokens": in_tok,
            "total_output_tokens": out_tok,
            "risk_breakdown": risk_breakdown,
            "hitl_events": hitl,
            "models_used": sorted(models),
        }
