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
LOW_CONFIDENCE_MULTI_TOKEN_PREFIXES = {
    "关于",
    "对于",
    "对於",
    "關於",
    "关于",
    "使用",
    "利用",
    "通过",
    "透过",
}
CONNECTOR_CHARACTERS = {"和", "與", "与", "及", "或", "跟", "且"}


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


def _is_connector_character(ch):
    return ch in CONNECTOR_CHARACTERS


def _contains_connector(text):
    return any(_is_connector_character(ch) for ch in text)


def _left_phrase_extension(text):
    if not text:
        return ""
    if _contains_connector(text):
        split_index = max(index for index, ch in enumerate(text) if _is_connector_character(ch))
        text = text[split_index + 1 :]
    while text and not _is_cjk_character(text[0]):
        text = text[1:]
    return text


def _right_phrase_extension(text):
    if not text:
        return ""
    index = 0
    while index < len(text) and _is_cjk_character(text[index]):
        index += 1
    if index == 0:
        return ""
    return text[:index]


def _is_phrase_boundary_marker(text):
    return any(_is_connector_character(ch) for ch in text) or any(not _is_cjk_character(ch) for ch in text)


def _is_safe_right_extension(text):
    if not text:
        return False
    if _contains_connector(text):
        return False
    index = 0
    while index < len(text) and _is_cjk_character(text[index]):
        index += 1
    if index != 1:
        return False
    return all(not ch.isalnum() and not _is_cjk_character(ch) for ch in text[index:])


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
    boundary_strength="strong",
    clean_local=False,
):
    if not source_text or not replacement_text:
        return "low"
    if source_text == replacement_text:
        return "low"
    if not clean_local:
        return "low"
    if _is_punctuation_only(source_text) or _is_punctuation_only(replacement_text):
        return "low"
    if len(source_text) == 1 or len(replacement_text) == 1:
        return "low"
    if boundary_strength != "strong":
        return "low"
    if len(source_text) >= 4 and (
        any(source_text.startswith(prefix) for prefix in LOW_CONFIDENCE_MULTI_TOKEN_PREFIXES)
        or any(replacement_text.startswith(prefix) for prefix in LOW_CONFIDENCE_MULTI_TOKEN_PREFIXES)
    ):
        return "low"
    if original_text is not None and start is not None and end is not None:
        if not _has_stable_local_boundaries(original_text, start, end):
            return "low"
    if candidate_text is not None and candidate_start is not None and candidate_end is not None:
        if not _has_stable_local_boundaries(candidate_text, candidate_start, candidate_end):
            return "low"
    return "high"


def _refine_single_character_change(original_text, candidate_text, opcodes, index, i1, i2, j1, j2):
    source_text = original_text[i1:i2]
    replacement_text = candidate_text[j1:j2]

    if len(source_text) == 1 and len(replacement_text) == 1:
        previous_opcode = opcodes[index - 1] if index > 0 else None
        next_opcode = opcodes[index + 1] if index + 1 < len(opcodes) else None

        if previous_opcode is not None and previous_opcode[0] == "equal":
            previous_text = original_text[previous_opcode[1] : previous_opcode[2]]
            left_extension = _left_phrase_extension(previous_text)
            if left_extension:
                start = i1 - len(left_extension)
                candidate_start = j1 - len(left_extension)
                return {
                    "source_text": original_text[start:i2],
                    "replacement_text": candidate_text[candidate_start:j2],
                    "start": start,
                    "end": i2,
                    "candidate_start": candidate_start,
                    "candidate_end": j2,
                    "boundary_strength": "strong",
                    "clean_local": True,
                }

        if next_opcode is not None and next_opcode[0] == "equal":
            next_text = original_text[next_opcode[1] : next_opcode[2]]
            if _is_safe_right_extension(next_text):
                right_extension = _right_phrase_extension(next_text)
                if right_extension:
                    end = i2 + len(right_extension)
                    candidate_end = j2 + len(right_extension)
                    return {
                        "source_text": original_text[i1:end],
                        "replacement_text": candidate_text[j1:candidate_end],
                        "start": i1,
                        "end": end,
                        "candidate_start": j1,
                        "candidate_end": candidate_end,
                        "boundary_strength": "strong",
                        "clean_local": True,
                    }

    if len(source_text) == 2 and len(replacement_text) == 2:
        if _contains_connector(source_text) or _contains_connector(replacement_text):
            return {
                "source_text": source_text,
                "replacement_text": replacement_text,
                "start": i1,
                "end": i2,
                "candidate_start": j1,
                "candidate_end": j2,
                "boundary_strength": "weak",
                "clean_local": False,
            }
        return {
            "source_text": source_text,
            "replacement_text": replacement_text,
            "start": i1,
            "end": i2,
            "candidate_start": j1,
            "candidate_end": j2,
            "boundary_strength": "strong",
            "clean_local": True,
        }

    return {
        "source_text": source_text,
        "replacement_text": replacement_text,
        "start": i1,
        "end": i2,
        "candidate_start": j1,
        "candidate_end": j2,
        "boundary_strength": "weak",
        "clean_local": False,
    }


def extract_variant_changes(original_text, candidate_text):
    matcher = difflib.SequenceMatcher(None, original_text, candidate_text)
    changes = []
    opcodes = matcher.get_opcodes()
    for index, (tag, i1, i2, j1, j2) in enumerate(opcodes):
        if tag == "equal":
            continue
        refined_change = _refine_single_character_change(
            original_text,
            candidate_text,
            opcodes,
            index,
            i1,
            i2,
            j1,
            j2,
        )
        if refined_change is None:
            continue
        source_text = refined_change["source_text"]
        replacement_text = refined_change["replacement_text"]

        change = {
            "source_text": source_text,
            "replacement_text": replacement_text,
            "confidence": classify_variant_change(
                source_text,
                replacement_text,
                original_text=original_text,
                candidate_text=candidate_text,
                start=refined_change["start"],
                end=refined_change["end"],
                candidate_start=refined_change["candidate_start"],
                candidate_end=refined_change["candidate_end"],
                boundary_strength=refined_change["boundary_strength"],
                clean_local=refined_change["clean_local"],
            ),
            "start": refined_change["start"],
            "end": refined_change["end"],
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
