# auditai

**EU AI Act Deployer Compliance SDK** — wrap Claude, GPT, Ollama or any OpenAI-compatible LLM and generate Article 26 reports in minutes.

[![PyPI](https://img.shields.io/pypi/v/auditai-sdk)](https://pypi.org/project/auditai-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Install

```bash
pip install auditai-sdk
```

## Quickstart

```python
from auditai import wrap_client
import anthropic

client = wrap_client(anthropic.Anthropic(), project="my-app")

# Your code stays identical — every call is now logged and risk-classified
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello"}],
)
```

## Supported providers

Works with any OpenAI-compatible API — including local LLMs:

```python
from openai import OpenAI
from auditai import wrap_client

# OpenAI
client = wrap_client(OpenAI(), project="my-app")

# Ollama (local)
client = wrap_client(
    OpenAI(base_url="http://localhost:11434/v1", api_key="ollama"),
    project="my-app"
)

# LM Studio (local)
client = wrap_client(
    OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio"),
    project="my-app"
)

# vLLM, llama.cpp, Azure OpenAI — same pattern
```

## CLI

```bash
# Risk classification wizard (9 questions → EU AI Act category)
auditai classify

# View call stats
auditai stats --project my-app

# Generate Article 26 Deployer Report (PDF)
auditai report --project my-app --company "Acme SL" --email "cto@acme.com"

# Launch Streamlit dashboard
auditai dashboard --project my-app
```

## What gets logged

Every AI call is recorded in a JSONL audit trail:

```json
{
  "call_id": "uuid",
  "timestamp": "2026-05-07T20:00:00Z",
  "provider": "anthropic",
  "model": "claude-sonnet-4-6",
  "input_tokens": 312,
  "output_tokens": 87,
  "input_hash": "sha256...",
  "output_preview": "first 100 chars...",
  "risk_category": "limited",
  "hitl_required": false
}
```

## Generate compliance report

```python
from auditai import generate_report

report_path = generate_report(
    project="my-app",
    company_name="Acme SL",
    contact_email="compliance@acme.com",
    extra_info={
        "system_description": "Customer support chatbot",
        "use_case": "Automated responses to user queries",
    },
)
# → EU_AI_Act_Report_my-app_2026-05-07.pdf
```

The report covers Art. 26 obligations: risk classification, technical evidence, HITL events, and deployer declaration.

## Links

- **Website:** [auditaisdk.com](https://auditaisdk.com)
- **PyPI:** [pypi.org/project/auditai-sdk](https://pypi.org/project/auditai-sdk/)
- **Contact:** [marc@auditaisdk.com](mailto:marc@auditaisdk.com)
