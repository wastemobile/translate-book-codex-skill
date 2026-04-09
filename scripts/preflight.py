#!/usr/bin/env python3
"""Preflight checks for the translate-book workflow."""

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib import request

from runtime_paths import resolve_api_key, resolve_glossary_db_path, resolve_python_executable


DEFAULT_STAGE2_MODEL = "gemma-4-e4b-it-8bit"
DEFAULT_STAGE3_MODEL = "gemma-4-26b-a4b-it-4bit"
DEFAULT_API_BASE = "http://127.0.0.1:8000/v1"

EXECUTABLE_CANDIDATES = {
    "ebook-convert": [
        "/Applications/calibre.app/Contents/MacOS/ebook-convert",
        "/usr/bin/ebook-convert",
        "/usr/local/bin/ebook-convert",
        "ebook-convert",
    ],
    "pandoc": [
        "/usr/bin/pandoc",
        "/usr/local/bin/pandoc",
        "pandoc",
    ],
}


def find_executable(name):
    for candidate in EXECUTABLE_CANDIDATES.get(name, [name]):
        resolved = shutil.which(candidate) if os.path.basename(candidate) == candidate else candidate
        if resolved and os.path.exists(resolved):
            return resolved
    return None


def find_python_module(name, python_executable=None):
    python_executable = python_executable or sys.executable
    if python_executable == sys.executable:
        return importlib.util.find_spec(name) is not None
    result = subprocess.run(
        [
            python_executable,
            "-c",
            (
                "import importlib.util, sys; "
                f"sys.exit(0 if importlib.util.find_spec({name!r}) is not None else 1)"
            ),
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def fetch_model_ids(api_base, api_key=None):
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = request.Request(
        f"{api_base.rstrip('/')}/models",
        headers=headers,
        method="GET",
    )
    with request.urlopen(req, timeout=30) as response:
        body = json.loads(response.read().decode("utf-8"))
    return [item["id"] for item in body.get("data", []) if item.get("id")]


def _add_check(report, name, status, detail):
    report["checks"].append({"name": name, "status": status, "detail": detail})
    report["summary"][status] += 1


def run_preflight(
    input_file,
    stage2_model=DEFAULT_STAGE2_MODEL,
    stage3_model=DEFAULT_STAGE3_MODEL,
    api_base=DEFAULT_API_BASE,
    api_key=None,
    python_executable=None,
    glossary_db=None,
    require_opencc=False,
):
    python_executable = python_executable or resolve_python_executable()
    glossary_db = glossary_db or resolve_glossary_db_path()
    api_key = resolve_api_key(api_key)
    report = {
        "status": "ok",
        "summary": {"ok": 0, "warn": 0, "fail": 0},
        "checks": [],
    }

    input_path = Path(input_file)
    if input_path.exists():
        _add_check(report, "input_file", "ok", str(input_path.resolve()))
    else:
        _add_check(report, "input_file", "fail", f"missing input file: {input_file}")

    workdir = Path.cwd()
    if os.access(workdir, os.W_OK):
        _add_check(report, "workdir_write", "ok", str(workdir))
    else:
        _add_check(report, "workdir_write", "fail", f"workdir not writable: {workdir}")

    for executable in ("pandoc", "ebook-convert"):
        resolved = find_executable(executable)
        if resolved:
            _add_check(report, executable, "ok", resolved)
        else:
            _add_check(report, executable, "fail", f"{executable} not found")

    _add_check(report, "python_executable", "ok", python_executable)

    module_checks = [
        ("pypandoc", "fail", "required for HTML <-> Markdown conversion"),
        ("bs4", "fail", "required for HTML parsing"),
        ("markdown", "fail", "required for HTML generation helpers"),
        ("opencc", "fail" if require_opencc else "warn", "required for zh-TW regional lexicon normalization" if require_opencc else "optional; needed for zh-TW regional lexicon normalization"),
    ]
    for module_name, missing_status, missing_detail in module_checks:
        if find_python_module(module_name, python_executable=python_executable):
            _add_check(report, module_name, "ok", f"python module '{module_name}' available")
        else:
            _add_check(report, module_name, missing_status, missing_detail)

    glossary_path = Path(glossary_db)
    if glossary_path.exists():
        _add_check(report, "glossary_db", "ok", str(glossary_path))
    else:
        _add_check(report, "glossary_db", "fail", f"missing glossary db: {glossary_db}")

    try:
        model_ids = fetch_model_ids(api_base, api_key=api_key)
        _add_check(report, "model_api", "ok", f"reachable: {api_base}")
        for name, model_id in (("stage2_model", stage2_model), ("stage3_model", stage3_model)):
            status = "ok" if model_id in model_ids else "fail"
            detail = model_id if status == "ok" else f"missing model id: {model_id}"
            _add_check(report, name, status, detail)
    except Exception as exc:  # pragma: no cover - network failure path exercised manually
        _add_check(report, "model_api", "fail", str(exc))
        _add_check(report, "stage2_model", "fail", f"unverified because model API failed: {stage2_model}")
        _add_check(report, "stage3_model", "fail", f"unverified because model API failed: {stage3_model}")

    if report["summary"]["fail"]:
        report["status"] = "fail"
    elif report["summary"]["warn"]:
        report["status"] = "warn"
    return report


def main():
    parser = argparse.ArgumentParser(description="Check whether the translate-book environment is ready.")
    parser.add_argument("--input-file", required=True)
    parser.add_argument("--stage2-model", default=DEFAULT_STAGE2_MODEL)
    parser.add_argument("--stage3-model", default=DEFAULT_STAGE3_MODEL)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--api-key", default=resolve_api_key())
    parser.add_argument("--python-executable", default=resolve_python_executable())
    parser.add_argument("--glossary-db", default=resolve_glossary_db_path())
    parser.add_argument("--require-opencc", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            run_preflight(
                input_file=args.input_file,
                stage2_model=args.stage2_model,
                stage3_model=args.stage3_model,
                api_base=args.api_base,
                api_key=args.api_key,
                python_executable=args.python_executable,
                glossary_db=args.glossary_db,
                require_opencc=args.require_opencc,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
