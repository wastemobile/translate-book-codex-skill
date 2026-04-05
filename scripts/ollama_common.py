#!/usr/bin/env python3
"""Shared helpers for local Ollama translation stages."""

import json
from pathlib import Path
from urllib import request


DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/generate"


def read_text(path):
    return Path(path).read_text(encoding="utf-8")


def write_text(path, content):
    Path(path).write_text(content, encoding="utf-8")


def post_generate(prompt, model, ollama_url=DEFAULT_OLLAMA_URL, options=None):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if options:
        payload["options"] = options

    req = request.Request(
        ollama_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=600) as response:
        body = json.loads(response.read().decode("utf-8"))
    return body["response"]
