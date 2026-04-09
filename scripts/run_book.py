#!/usr/bin/env python3
"""Single-entry orchestration for the translate-book workflow."""

import argparse
import json
import os
import subprocess
from pathlib import Path

import preflight


DEFAULT_TARGET_LANG = "zh-TW"
DEFAULT_OUTPUT_FORMATS = "epub"
DEFAULT_PROVIDER = "omlx"
DEFAULT_API_BASE = "http://127.0.0.1:8000/v1"
# Model IDs must match the names served by the local model runtime (oMLX/Ollama).
# These values align with the defaults in ollama_stage_translate.py and
# ollama_stage_refine.py so that preflight validates the same IDs the stages use.
DEFAULT_STAGE2_MODEL = "gemma-4-e4b-it-8bit"
DEFAULT_STAGE3_MODEL = "gemma-4-26b-a4b-it-4bit"


def derive_temp_dir(input_file):
    path = Path(input_file)
    return str(path.with_suffix("")) + "_temp"


def run_step(step_name, command):
    try:
        subprocess.run(command, check=True)
        return {"name": step_name, "status": "ok", "command": command}
    except subprocess.CalledProcessError as exc:
        return {"name": step_name, "status": "fail", "error": str(exc), "command": command}


def run_pipeline(
    input_file,
    target_lang=DEFAULT_TARGET_LANG,
    output_formats=DEFAULT_OUTPUT_FORMATS,
    provider=DEFAULT_PROVIDER,
    api_base=DEFAULT_API_BASE,
    api_key=None,
    stage2_model=DEFAULT_STAGE2_MODEL,
    stage3_model=DEFAULT_STAGE3_MODEL,
    parallelism=1,
):
    preflight_report = preflight.run_preflight(
        input_file=input_file,
        stage2_model=stage2_model,
        stage3_model=stage3_model,
        api_base=api_base,
        api_key=api_key,
    )
    if preflight_report["status"] == "fail":
        return {"status": "fail", "preflight": preflight_report, "steps": []}

    temp_dir = derive_temp_dir(input_file)
    steps = []

    convert_command = [
        "python3",
        str(Path(__file__).with_name("convert.py")),
        input_file,
        "--olang",
        target_lang,
    ]
    step = run_step("convert", convert_command)
    steps.append(step)
    if step.get("status") == "fail":
        return {"status": "fail", "preflight": preflight_report, "temp_dir": temp_dir, "steps": steps}

    draft_command = [
        "python3",
        str(Path(__file__).with_name("ollama_stage_translate.py")),
        "--temp-dir",
        temp_dir,
        "--target-lang",
        "Traditional Chinese" if target_lang == "zh-TW" else target_lang,
        "--model",
        stage2_model,
        "--provider",
        provider,
        "--api-base",
        api_base,
        "--parallelism",
        str(parallelism),
    ]
    if api_key:
        draft_command.extend(["--api-key", api_key])
    step = run_step("draft", draft_command)
    steps.append(step)
    if step.get("status") == "fail":
        return {"status": "fail", "preflight": preflight_report, "temp_dir": temp_dir, "steps": steps}

    refine_command = [
        "python3",
        str(Path(__file__).with_name("ollama_stage_refine.py")),
        "--temp-dir",
        temp_dir,
        "--target-lang",
        "Traditional Chinese" if target_lang == "zh-TW" else target_lang,
        "--model",
        stage3_model,
        "--provider",
        provider,
        "--api-base",
        api_base,
        "--parallelism",
        str(parallelism),
    ]
    if api_key:
        refine_command.extend(["--api-key", api_key])
    step = run_step("refine", refine_command)
    steps.append(step)
    if step.get("status") == "fail":
        return {"status": "fail", "preflight": preflight_report, "temp_dir": temp_dir, "steps": steps}

    audit_command = [
        "python3",
        str(Path(__file__).with_name("chunk_audit.py")),
        "--temp-dir",
        temp_dir,
        "--promote",
    ]
    step = run_step("audit", audit_command)
    steps.append(step)
    if step.get("status") == "fail":
        return {"status": "fail", "preflight": preflight_report, "temp_dir": temp_dir, "steps": steps}

    merge_command = [
        "python3",
        str(Path(__file__).with_name("merge_and_build.py")),
        "--temp-dir",
        temp_dir,
        "--lang",
        target_lang,
        "--formats",
        output_formats,
    ]
    step = run_step("merge", merge_command)
    steps.append(step)
    if step.get("status") == "fail":
        return {"status": "fail", "preflight": preflight_report, "temp_dir": temp_dir, "steps": steps}

    status = "warn" if preflight_report["status"] == "warn" else "ok"
    return {
        "status": status,
        "preflight": preflight_report,
        "temp_dir": temp_dir,
        "steps": steps,
    }


def main():
    parser = argparse.ArgumentParser(description="Run the translate-book workflow with sensible defaults.")
    parser.add_argument("--input-file", required=True)
    parser.add_argument("--target-lang", default=DEFAULT_TARGET_LANG)
    parser.add_argument("--output-formats", default=DEFAULT_OUTPUT_FORMATS)
    parser.add_argument("--provider", default=DEFAULT_PROVIDER)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--stage2-model", default=DEFAULT_STAGE2_MODEL)
    parser.add_argument("--stage3-model", default=DEFAULT_STAGE3_MODEL)
    parser.add_argument("--parallelism", type=int, default=1)
    args = parser.parse_args()
    print(
        json.dumps(
            run_pipeline(
                input_file=args.input_file,
                target_lang=args.target_lang,
                output_formats=args.output_formats,
                provider=args.provider,
                api_base=args.api_base,
                api_key=args.api_key,
                stage2_model=args.stage2_model,
                stage3_model=args.stage3_model,
                parallelism=args.parallelism,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
