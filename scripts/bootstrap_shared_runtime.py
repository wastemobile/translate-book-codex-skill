#!/usr/bin/env python3
"""Bootstrap the shared Codex runtime for the translate-book skill."""

import argparse
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

from runtime_paths import (
    CODEX_HOME,
    DEFAULT_GLOSSARY_DB,
    DEFAULT_SHARED_DATA_DIR,
    DEFAULT_SHARED_VENV,
    TRANSLATE_BOOK_HOME,
)


def ensure_venv(venv_path):
    if not venv_path.exists():
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
    python_executable = venv_path / "bin" / "python3"
    pip_executable = [str(python_executable), "-m", "pip"]
    subprocess.run(pip_executable + ["install", "--upgrade", "pip"], check=True)
    subprocess.run(
        pip_executable
        + ["install", "-r", str(Path(__file__).resolve().parents[1] / "requirements.txt")],
        check=True,
    )
    return python_executable


def ensure_skill_symlink(repo_root):
    skills_dir = CODEX_HOME / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    target = skills_dir / "translate-book"
    if target.is_symlink() or target.exists():
        if target.is_symlink() and Path(os.readlink(target)).resolve() == repo_root.resolve():
            return target
        target.unlink()
    target.symlink_to(repo_root)
    return target


def ensure_glossary_db(glossary_db, seed_glossary_from=None):
    glossary_db.parent.mkdir(parents=True, exist_ok=True)
    if glossary_db.exists():
        return glossary_db
    if seed_glossary_from:
        shutil.copy2(seed_glossary_from, glossary_db)
        return glossary_db
    with sqlite3.connect(glossary_db) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS terms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_term TEXT NOT NULL,
                target_term TEXT NOT NULL,
                normalized_source TEXT NOT NULL,
                domain TEXT,
                dataset TEXT,
                note TEXT,
                source_lang TEXT NOT NULL,
                target_lang TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 100,
                source_file TEXT,
                row_hash TEXT NOT NULL UNIQUE
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_terms_lookup
            ON terms(normalized_source, dataset, domain)
            """
        )
    return glossary_db


def main():
    parser = argparse.ArgumentParser(description="Bootstrap the shared translate-book Codex runtime.")
    parser.add_argument("--seed-glossary-from", default=None)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    TRANSLATE_BOOK_HOME.mkdir(parents=True, exist_ok=True)
    DEFAULT_SHARED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    python_executable = ensure_venv(DEFAULT_SHARED_VENV)
    skill_link = ensure_skill_symlink(repo_root)
    glossary_db = ensure_glossary_db(
        DEFAULT_GLOSSARY_DB,
        seed_glossary_from=Path(args.seed_glossary_from).expanduser() if args.seed_glossary_from else None,
    )

    print(f"shared_home={TRANSLATE_BOOK_HOME}")
    print(f"python={python_executable}")
    print(f"skill_symlink={skill_link} -> {repo_root}")
    print(f"glossary_db={glossary_db}")


if __name__ == "__main__":
    main()
