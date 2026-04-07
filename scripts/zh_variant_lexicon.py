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


def _is_punctuation_only(text):
    return not any(_is_cjk_character(ch) or ch.isalnum() for ch in text)


def _has_stable_local_boundaries(text, start, end):
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    return not (
        (before and before.isascii() and before.isalnum())
        or (after and after.isascii() and after.isalnum())
    )


def build_converter(config=DEFAULT_OPENCC_CONFIG):
    if opencc is None:
        return None
    return opencc.OpenCC(config)


def generate_opencc_candidate(text, config=DEFAULT_OPENCC_CONFIG):
    converter = build_converter(config)
    if converter is None:
        return text
    return converter.convert(text)


def classify_variant_change(
    source_text,
    replacement_text,
    original_text=None,
    candidate_text=None,
    start=None,
    end=None,
    candidate_start=None,
    candidate_end=None,
):
    if not source_text or not replacement_text:
        return "low"
    if source_text == replacement_text:
        return "low"
    if _is_punctuation_only(source_text) or _is_punctuation_only(replacement_text):
        return "low"
    if len(source_text) == 1 or len(replacement_text) == 1:
        return "low"
    if original_text is not None and start is not None and end is not None:
        if not _has_stable_local_boundaries(original_text, start, end):
            return "low"
    if candidate_text is not None and candidate_start is not None and candidate_end is not None:
        if not _has_stable_local_boundaries(candidate_text, candidate_start, candidate_end):
            return "low"
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
            "confidence": classify_variant_change(
                source_text,
                replacement_text,
                original_text=original_text,
                candidate_text=candidate_text,
                start=i1,
                end=i2,
                candidate_start=j1,
                candidate_end=j2,
            ),
            "start": i1,
            "end": i2,
        }
        changes.append(change)
    return changes


def apply_high_confidence_variant_fixes(text, changes):
    fixed = text
    regional_auto_fixes = [item for item in changes if item.get("confidence") == "high"]
    regional_flagged_variants = [item for item in changes if item.get("confidence") != "high"]

    for change in sorted(regional_auto_fixes, key=lambda item: item["start"], reverse=True):
        start = change["start"]
        end = change["end"]
        fixed = fixed[:start] + change["replacement_text"] + fixed[end:]
    return {
        "normalized_text": fixed,
        "regional_auto_fixes": regional_auto_fixes,
        "regional_flagged_variants": regional_flagged_variants,
    }


def normalize_with_opencc(text, config=DEFAULT_OPENCC_CONFIG):
    candidate_text = generate_opencc_candidate(text, config=config)
    variant_changes = extract_variant_changes(text, candidate_text)
    fix_result = apply_high_confidence_variant_fixes(text, variant_changes)
    normalized_text = fix_result["normalized_text"]
    return {
        "original_text": text,
        "candidate_text": candidate_text,
        "config": config,
        "opencc_available": opencc is not None,
        "changed": normalized_text != text,
        "variant_changes": variant_changes,
        "regional_auto_fixes": fix_result["regional_auto_fixes"],
        "regional_flagged_variants": fix_result["regional_flagged_variants"],
        "normalized_text": normalized_text,
    }
