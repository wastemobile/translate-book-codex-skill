#!/usr/bin/env python3
"""Preflight checks for the translate-book workflow."""

import argparse
import importlib.util
import json
import os
import shutil
from pathlib import Path
from urllib import request


# Model IDs must match the names served by the local model runtime.
# Aligned with ollama_stage_translate.py and ollama_stage_refine.py defaults.
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


def find_python_module(name):
    return importlib.util.find_spec(name) is not None


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
):
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

    module_checks = [
        ("pypandoc", "fail", "required for HTML <-> Markdown conversion"),
        ("bs4", "warn", "recommended for HTML parsing"),
        ("markdown", "warn", "recommended for HTML generation helpers"),
        ("opencc", "warn", "optional; needed for zh-TW regional lexicon normalization"),
    ]
    for module_name, missing_status, missing_detail in module_checks:
        if find_python_module(module_name):
            _add_check(report, module_name, "ok", f"python module '{module_name}' available")
        else:
            _add_check(report, module_name, missing_status, missing_detail)

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
    parser.add_argument("--api-key", default=None)
    args = parser.parse_args()
    print(
        json.dumps(
            run_preflight(
                input_file=args.input_file,
                stage2_model=args.stage2_model,
                stage3_model=args.stage3_model,
                api_base=args.api_base,
                api_key=args.api_key,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
