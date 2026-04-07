#!/usr/bin/env python3
"""OpenCC-backed helpers for zh-CN to zh-TW lexical normalization."""

try:
    import opencc  # type: ignore
except ImportError:  # pragma: no cover - exercised when the dependency is absent
    opencc = None


DEFAULT_OPENCC_CONFIG = "t2tw"


def build_converter(config=DEFAULT_OPENCC_CONFIG):
    if opencc is None:
        return None
    return opencc.OpenCC(config)


def generate_opencc_candidate(text, config=DEFAULT_OPENCC_CONFIG):
    converter = build_converter(config)
    if converter is None:
        return text
    return converter.convert(text)


def normalize_with_opencc(text, config=DEFAULT_OPENCC_CONFIG):
    candidate_text = generate_opencc_candidate(text, config=config)
    return {
        "original_text": text,
        "candidate_text": candidate_text,
        "config": config,
        "opencc_available": opencc is not None,
        "changed": candidate_text != text,
    }

