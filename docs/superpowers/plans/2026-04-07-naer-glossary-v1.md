# NAER Glossary V1

Date: `2026-04-07`

## Purpose

Establish a first usable glossary system for long-form book translation, using NAER terminology downloads as a controlled reference source instead of raw prompt stuffing.

This document is the handoff and memory record for the `naer-glossary-prototype` worktree branch.

## V1 Status

Glossary support is considered `v1 complete` at the infrastructure level.

Included in v1:

- NAER `.zip` download support
- `.ods` extraction and parsing without LibreOffice
- normalized glossary import into local `SQLite`
- multi-dataset storage in one database
- chunk-level glossary retrieval
- prompt-ready glossary block rendering
- Stage 2 glossary injection
- Stage 3 glossary injection
- `chunk_audit.py` glossary mismatch checks
- dataset auto-selection per chunk
- high-confidence terminology filtering
- glossary repair pass with output safety checks

Not considered complete in v1:

- stable automatic mismatch repair quality across real books
- hard terminology enforcement
- semantic disambiguation across ambiguous single-word terms
- domain inference beyond hit-count heuristics

## Branch And Commits

Worktree:

- `.worktrees/naer-glossary-prototype`

Key commits:

- `627dfff` `feat: add NAER glossary integration pipeline`
- `5074197` `feat: auto-select glossary datasets per chunk`
- `f52a4a3` `fix: harden glossary repair matching`
- `392c4af` `feat: add bulk NAER glossary import`
- `175d5ef` `feat: add regional lexicon audit integration`
- `1b86f37` `fix: expose regional backend availability in audits`
- `474adaf` `docs: clarify opencc dependency for regional audit`

## Data And Validation Used

Real NAER datasets imported during development:

- `電子計算機名詞`: `9993` rows
- `電機工程名詞`: `9960` rows

Representative real-book validation source:

- `~/lab/stories/What the Dormouse Said.epub`

Converted test book temp directory:

- `What the Dormouse Said_temp`

Representative inspected chunks:

- `chunk0017.md`
- `chunk0030.md`
- `chunk0042.md`

## What Worked

- The glossary pipeline works end to end from NAER source files to translation-stage prompt injection.
- Multi-dataset lookup works and respects left-to-right dataset priority.
- Auto-select can rank likely datasets for a chunk.
- High-confidence filtering substantially reduces noisy prompt pollution in narrative nonfiction.
- Audit can report `term_mismatch` cases for review.
- Repair now has safety guards:
  - it strips obvious preface noise from model output only when the original translation anchor is preserved
  - it rejects repair candidates unless mismatch count actually improves

## Real-Book Findings

`What the Dormouse Said` was intentionally useful because it exposed failure modes that unit tests would not catch.

Observed findings:

- naive glossary injection was too noisy for history-of-technology prose
- generic single words needed aggressive filtering
- mixed-case hyphenated terms such as `A-law` could be falsely matched unless case-sensitive boundary checks were added
- prompt-only repair is not yet strong enough to guarantee terminology correction on narrative chunks

Current interpretation:

- glossary lookup and audit are production-usable as `reference + QA`
- glossary repair remains experimental

## Regional Lexicon Audit Validation

An audit-stage `zh-CN` to `zh-TW` regional lexicon normalization pass was also validated on real translated output from `What the Dormouse Said`, using these three existing translation variants of `chunk0017`:

- `test-output/dormouse-ab/chunk0017.baseline.md`
- `test-output/dormouse-ab/chunk0017.glossary.md`
- `test-output/dormouse-ab/chunk0017.repaired.md`

Validation command pattern:

- `.venv/bin/python scripts/chunk_audit.py --temp-dir <sample-dir> --regional-lexicon-config s2twp --regional-lexicon-auto-fix --regional-lexicon-report`

Observed behavior:

- the OpenCC-backed pass correctly reported `regional_opencc_available: True` when run from the project venv
- the baseline chunk surfaced both `residual_english` and `regional_lexicon`
- the glossary chunk surfaced only `regional_lexicon`
- the repaired chunk kept failing on `residual_english`, but the regional pass still applied useful fixes
- repeated high-confidence fixes were directionally correct for Taiwan usage, including:
  - `矽芯片 -> 矽晶片`
  - `集成電路 -> 積體電路`
  - `自動櫃員機網絡 -> 自動櫃員機網路`
  - `設備 -> 裝置`
- low-confidence findings remained report-only, for example:
  - `項目 -> 專案`

Important limitation exposed by this validation:

- some `regional_auto_fixes` spans are still wider than ideal in the structured report, even when the resulting normalized text is correct
- this means the text-level normalization is already useful, but the per-fix reporting UX still needs refinement before being treated as polished

## Operational Guidance

Recommended default usage for now:

- enable glossary references during Stage 2 and Stage 3
- enable glossary mismatch audit
- treat repair as optional or experimental

Do not assume yet:

- that repair will reliably reduce mismatches on every book
- that any glossary hit should be hard-enforced
- that dataset auto-select is equivalent to domain understanding

## Known Limits

- `expected_target` is still matched as a literal string; multi-translation forms such as `人造智慧；人工智慧` are not yet split into alternative accepted forms
- repair depends on model compliance and can still be ineffective even when safety checks prevent degradation
- dataset ranking is still based on hit count and coverage, not contextual meaning
- narrative books and technical manuals likely need different confidence thresholds in a future version

## Next Iteration Priorities

Recommended order for v1.x / v2 work:

1. import 3 to 5 more NAER datasets with clearly different domains
2. validate on different book types:
   - technical manuals
   - popular science
   - technology history / biography / narrative nonfiction
3. refine mismatch logic so a glossary entry with multiple acceptable Chinese forms can pass if any allowed form appears
4. improve dataset ranking beyond raw hit count
5. explore tighter local repair strategies:
   - sentence-level targeted repair
   - span-level replacement plus local smoothing
   - context-window repair around only the mismatched sentence

## Verification Snapshot

At the time this document was written:

- `python3 -m unittest discover -s tests` passed with `91 tests`

This confirms code correctness for the current branch state, but not final translation-quality sufficiency.
