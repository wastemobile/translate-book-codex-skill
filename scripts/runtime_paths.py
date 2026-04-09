#!/usr/bin/env python3
"""Shared runtime paths for the globally-installed translate-book skill."""

import os
import sys
from pathlib import Path


CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
TRANSLATE_BOOK_HOME = Path(
    os.environ.get("TRANSLATE_BOOK_HOME", CODEX_HOME / "translate-book")
).expanduser()
DEFAULT_SHARED_VENV = TRANSLATE_BOOK_HOME / ".venv"
DEFAULT_SHARED_PYTHON = DEFAULT_SHARED_VENV / "bin" / "python3"
DEFAULT_SHARED_DATA_DIR = TRANSLATE_BOOK_HOME / "data"
DEFAULT_GLOSSARY_DB = Path(
    os.environ.get("TRANSLATE_BOOK_GLOSSARY_DB", DEFAULT_SHARED_DATA_DIR / "terms.sqlite3")
).expanduser()


def resolve_python_executable():
    override = os.environ.get("TRANSLATE_BOOK_PYTHON")
    if override:
        return override
    if DEFAULT_SHARED_PYTHON.exists():
        return str(DEFAULT_SHARED_PYTHON)
    return sys.executable


def resolve_glossary_db_path():
    override = os.environ.get("TRANSLATE_BOOK_GLOSSARY_DB")
    if override:
        return override
    return str(DEFAULT_GLOSSARY_DB)


def resolve_api_key(explicit=None):
    if explicit is not None:
        return explicit
    return os.environ.get("LOCAL_LLM_API_KEY")
