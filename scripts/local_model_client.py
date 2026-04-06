#!/usr/bin/env python3
"""Shared helpers for provider-flexible local model generation."""

import json
import os
from pathlib import Path
from urllib import request


DEFAULT_PROVIDER = "omlx"
DEFAULT_OMLX_API_BASE = "http://127.0.0.1:8000/v1"
DEFAULT_OLLAMA_API_BASE = "http://127.0.0.1:11434/api/generate"


def read_text(path):
    return Path(path).read_text(encoding="utf-8")


def write_text(path, content):
    Path(path).write_text(content, encoding="utf-8")


def resolve_client_config(provider=None, api_base=None, api_key=None):
    resolved_provider = provider or os.environ.get("LOCAL_LLM_PROVIDER") or DEFAULT_PROVIDER
    resolved_provider = resolved_provider.lower()
    if resolved_provider not in {"omlx", "ollama"}:
        raise ValueError(f"unsupported local model provider: {resolved_provider}")

    resolved_api_base = api_base or os.environ.get("LOCAL_LLM_API_BASE")
    if not resolved_api_base:
        resolved_api_base = (
            DEFAULT_OMLX_API_BASE if resolved_provider == "omlx" else DEFAULT_OLLAMA_API_BASE
        )

    resolved_api_key = api_key if api_key is not None else os.environ.get("LOCAL_LLM_API_KEY")
    return {
        "provider": resolved_provider,
        "api_base": resolved_api_base,
        "api_key": resolved_api_key,
    }


def _post_json(url, payload, headers=None):
    merged_headers = {"Content-Type": "application/json"}
    if headers:
        merged_headers.update(headers)

    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=merged_headers,
        method="POST",
    )
    with request.urlopen(req, timeout=600) as response:
        return json.loads(response.read().decode("utf-8"))


def _generate_with_omlx(prompt, model, api_base, api_key=None, temperature=None):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    if temperature is not None:
        payload["temperature"] = temperature

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    body = _post_json(f"{api_base.rstrip('/')}/chat/completions", payload, headers=headers)
    return body["choices"][0]["message"]["content"]


def _generate_with_ollama(prompt, model, api_base, temperature=None):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if temperature is not None:
        payload["options"] = {"temperature": temperature}

    body = _post_json(api_base, payload)
    return body["response"]


def generate_text(prompt, model, provider=None, api_base=None, api_key=None, temperature=None):
    config = resolve_client_config(provider=provider, api_base=api_base, api_key=api_key)
    if config["provider"] == "omlx":
        return _generate_with_omlx(
            prompt,
            model=model,
            api_base=config["api_base"],
            api_key=config["api_key"],
            temperature=temperature,
        )
    return _generate_with_ollama(
        prompt,
        model=model,
        api_base=config["api_base"],
        temperature=temperature,
    )
