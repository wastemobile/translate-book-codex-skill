#!/usr/bin/env python3
"""Backward-compatible wrappers for legacy Ollama helper imports."""

from local_model_client import DEFAULT_OLLAMA_API_BASE, read_text, write_text


DEFAULT_OLLAMA_URL = DEFAULT_OLLAMA_API_BASE


def post_generate(prompt, model, ollama_url=DEFAULT_OLLAMA_URL, options=None):
    temperature = None
    if options:
        temperature = options.get("temperature")
    from local_model_client import generate_text

    return generate_text(
        prompt,
        model=model,
        provider="ollama",
        api_base=ollama_url,
        temperature=temperature,
    )
