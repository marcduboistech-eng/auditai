"""Transparent HTTP proxy — intercept OpenAI-compatible API calls for EU AI Act logging.

Usage:
    auditai proxy --port 8080 --target https://api.openai.com --project my-app

Then point your client at localhost:8080:
    client = openai.OpenAI(base_url="http://localhost:8080/v1", api_key="...")

Works with any OpenAI-compatible API: OpenAI, Anthropic (via proxy), Ollama, vLLM, LM Studio.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

from .logger import AuditLogger
from .risk import RiskClassifier


def _extract_openai_fields(body: dict) -> tuple[str, list, str]:
    """Extract model, messages, output_text from an OpenAI-compatible response."""
    model = body.get("model", "unknown")
    messages = body.get("messages", [])
    return model, messages, ""


def _extract_openai_response(resp_body: dict) -> tuple[str, int, int]:
    output_text = ""
    input_tokens = 0
    output_tokens = 0
    choices = resp_body.get("choices", [])
    if choices:
        msg = choices[0].get("message", {})
        output_text = msg.get("content", "") or ""
    usage = resp_body.get("usage", {})
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)
    return output_text, input_tokens, output_tokens


def _extract_anthropic_response(resp_body: dict) -> tuple[str, int, int]:
    output_text = ""
    for block in resp_body.get("content", []):
        if block.get("type") == "text":
            output_text += block.get("text", "")
    usage = resp_body.get("usage", {})
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    return output_text, input_tokens, output_tokens


def make_handler(target: str, logger: AuditLogger, classifier: RiskClassifier):
    class ProxyHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # silence default HTTP server logs

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length) if length else b"{}"
            try:
                req_body = json.loads(raw_body)
            except Exception:
                req_body = {}

            # Build upstream request
            upstream_url = target.rstrip("/") + self.path
            upstream_headers = {
                k: v for k, v in self.headers.items()
                if k.lower() not in ("host", "content-length", "transfer-encoding")
            }
            upstream_headers["Content-Type"] = "application/json"

            upstream_req = urllib.request.Request(
                upstream_url, data=raw_body, headers=upstream_headers, method="POST"
            )

            resp_body: dict = {}
            status_code = 200
            resp_raw = b""
            try:
                with urllib.request.urlopen(upstream_req, timeout=120) as resp:
                    status_code = resp.status
                    resp_raw = resp.read()
                    resp_body = json.loads(resp_raw)
            except urllib.error.HTTPError as e:
                status_code = e.code
                resp_raw = e.read()
                try:
                    resp_body = json.loads(resp_raw)
                except Exception:
                    resp_body = {}

            # Determine provider from path
            is_anthropic = "/messages" in self.path and "/chat" not in self.path
            model = req_body.get("model", "unknown")
            messages = req_body.get("messages", [])
            if messages is None:
                messages = []

            if is_anthropic:
                output_text, in_tok, out_tok = _extract_anthropic_response(resp_body)
            else:
                output_text, in_tok, out_tok = _extract_openai_response(resp_body)

            risk_cat = classifier.classify_call(
                model=model, input_messages=messages, output_text=output_text
            )
            logger.log_call(
                model=model,
                provider=f"proxy-{'anthropic' if is_anthropic else 'openai'}",
                input_messages=messages,
                output_text=output_text,
                input_tokens=in_tok,
                output_tokens=out_tok,
                risk_category=str(risk_cat),
                hitl_required=risk_cat in ("high", "unacceptable"),
                metadata={"path": self.path, "status": status_code},
            )

            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_raw)))
            self.end_headers()
            self.wfile.write(resp_raw)

        def do_GET(self):
            # Pass-through GET (e.g. health checks, model listing)
            upstream_url = target.rstrip("/") + self.path
            upstream_headers = {
                k: v for k, v in self.headers.items()
                if k.lower() not in ("host",)
            }
            try:
                req = urllib.request.Request(upstream_url, headers=upstream_headers)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw = resp.read()
                    self.send_response(resp.status)
                    self.send_header("Content-Type", resp.headers.get("Content-Type", "application/json"))
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
            except Exception as e:
                self.send_error(502, str(e))

    return ProxyHandler


def run_proxy(
    target: str,
    project: str,
    port: int = 8080,
    log_dir: Optional[str] = None,
) -> None:
    logger = AuditLogger(project=project, log_dir=log_dir)
    classifier = RiskClassifier()
    handler = make_handler(target, logger, classifier)
    server = HTTPServer(("0.0.0.0", port), handler)
    print(f"auditai proxy → :{port} → {target}  [project={project}]")
    print(f"Logs: {logger.log_path}")
    print("Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nProxy stopped.")
