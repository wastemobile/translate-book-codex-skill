#!/usr/bin/env python3
"""OpenCC-backed helpers for zh-CN to zh-TW lexical normalization."""

import difflib

try:
    import opencc  # type: ignore
except ImportError:  # pragma: no cover - exercised when the dependency is absent
    opencc = None


# Use the simplified-to-Taiwan configuration because the input we normalize is
# usually Mainland-flavored translation output, not already-traditional text.
DEFAULT_OPENCC_CONFIG = "s2twp"


def _is_cjk_character(ch):
    return "\u4e00" <= ch <= "\u9fff"


def build_converter(config=DEFAULT_OPENCC_CONFIG):
    if opencc is None:
        return None
    return opencc.OpenCC(config)


def generate_opencc_candidate(text, config=DEFAULT_OPENCC_CONFIG):
    converter = build_converter(config)
    if converter is None:
        return text
    return converter.convert(text)


def classify_variant_change(source_text, replacement_text):
    if not source_text or not replacement_text:
        return "low"
    if len(source_text) == 1 or len(replacement_text) == 1:
        return "low"
    if len(source_text) != len(replacement_text):
        return "high"
    return "high"


def extract_variant_changes(original_text, candidate_text):
    matcher = difflib.SequenceMatcher(None, original_text, candidate_text)
    changes = []
    opcodes = matcher.get_opcodes()
    for index, (tag, i1, i2, j1, j2) in enumerate(opcodes):
        if tag == "equal":
            continue
        source_text = original_text[i1:i2]
        replacement_text = candidate_text[j1:j2]

        if len(source_text) == 1 and len(replacement_text) == 1:
            prev_opcode = opcodes[index - 1] if index > 0 else None
            next_opcode = opcodes[index + 1] if index + 1 < len(opcodes) else None

            if (
                prev_opcode
                and prev_opcode[0] == "equal"
                and prev_opcode[2] - prev_opcode[1] >= 2
                and prev_opcode[4] - prev_opcode[3] >= 2
            ):
                prev_source = original_text[prev_opcode[1] : prev_opcode[2]]
                prev_replacement = candidate_text[prev_opcode[3] : prev_opcode[4]]
                source_text = prev_source + source_text
                replacement_text = prev_replacement + replacement_text
                i1 = prev_opcode[1]
                j1 = prev_opcode[3]
            elif (
                next_opcode
                and next_opcode[0] == "equal"
                and next_opcode[2] - next_opcode[1] >= 1
                and next_opcode[4] - next_opcode[3] >= 1
                and _is_cjk_character(original_text[next_opcode[1]])
                and _is_cjk_character(candidate_text[next_opcode[3]])
            ):
                next_source = original_text[next_opcode[1] : next_opcode[2]]
                next_replacement = candidate_text[next_opcode[3] : next_opcode[4]]
                source_text = source_text + next_source[:1]
                replacement_text = replacement_text + next_replacement[:1]
                i2 = i1 + len(source_text)
                j2 = j1 + len(replacement_text)

        change = {
            "source_text": source_text,
            "replacement_text": replacement_text,
            "confidence": classify_variant_change(source_text, replacement_text),
            "start": i1,
            "end": i2,
        }
        changes.append(change)
    return changes


def apply_high_confidence_variant_fixes(text, changes):
    fixed = text
    for change in sorted(changes, key=lambda item: item["start"], reverse=True):
        if change.get("confidence") != "high":
            continue
        start = change["start"]
        end = change["end"]
        fixed = fixed[:start] + change["replacement_text"] + fixed[end:]
    return fixed


def normalize_with_opencc(text, config=DEFAULT_OPENCC_CONFIG):
    candidate_text = generate_opencc_candidate(text, config=config)
    variant_changes = extract_variant_changes(text, candidate_text)
    regional_auto_fixes = [item for item in variant_changes if item["confidence"] == "high"]
    regional_flagged_variants = [item for item in variant_changes if item["confidence"] != "high"]
    normalized_text = apply_high_confidence_variant_fixes(text, variant_changes)
    return {
        "original_text": text,
        "candidate_text": candidate_text,
        "config": config,
        "opencc_available": opencc is not None,
        "changed": normalized_text != text,
        "variant_changes": variant_changes,
        "regional_auto_fixes": regional_auto_fixes,
        "regional_flagged_variants": regional_flagged_variants,
        "normalized_text": normalized_text,
    }
