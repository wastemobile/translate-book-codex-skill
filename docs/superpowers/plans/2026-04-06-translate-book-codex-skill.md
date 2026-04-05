# Translate-Book Codex Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable Codex skill that ports the original `translate-book` Claude skill, preserves the Calibre/Pandoc-based preprocessing and packaging workflow, and replaces the translation middle stage with a four-stage hybrid pipeline using Codex + local Ollama models.

**Architecture:** The skill lives in `~/.codex/skills/translate-book/` but is developed in this repository. The existing Python conversion and build scripts are vendored with minimal behavior changes, while new orchestration scripts manage draft/refine/audit stages and the SKILL instructs Codex to handle the sample and final-review stages interactively. Final artifacts are still produced through `merge_and_build.py`.

**Tech Stack:** Python 3, Pandoc via `pypandoc`, Calibre `ebook-convert`, Markdown, BeautifulSoup, git, Codex skills metadata, local Ollama HTTP API.

---

### Task 1: Scaffold the Skill Repository

**Files:**
- Create: `SKILL.md`
- Create: `agents/openai.yaml`
- Create: `scripts/`
- Create: `tests/`
- Create: `.gitignore`
- Modify: `docs/superpowers/specs/2026-04-06-translate-book-codex-skill-design.md`
- Test: repository tree inspection

- [ ] **Step 1: Create the base directory structure**

Create:
- `agents/`
- `scripts/`
- `tests/`

- [ ] **Step 2: Add a minimal `.gitignore`**

Include Python cache files, temp ebook build artifacts, and local test outputs.

- [ ] **Step 3: Draft `SKILL.md` frontmatter and top-level workflow**

Include:
- skill name and description
- required binaries and Python dependencies
- four-stage translation workflow
- chunk naming lifecycle
- low-concurrency guidance

- [ ] **Step 4: Generate `agents/openai.yaml`**

Provide:
- display name
- short description
- default prompt aligned to book translation

- [ ] **Step 5: Verify the repository structure**

Run: `find . -maxdepth 2 -type f | sort`
Expected: top-level skill files and empty scaffolding paths are present.

- [ ] **Step 6: Commit**

```bash
git add .gitignore SKILL.md agents/openai.yaml docs/superpowers/specs/2026-04-06-translate-book-codex-skill-design.md
git commit -m "chore: scaffold translate-book codex skill"
```

### Task 2: Vendor the Existing Conversion and Packaging Pipeline

**Files:**
- Create: `scripts/convert.py`
- Create: `scripts/manifest.py`
- Create: `scripts/merge_and_build.py`
- Create: `scripts/calibre_html_publish.py`
- Create: `scripts/template.html`
- Create: `scripts/template_ebook.html`
- Test: `tests/test_convert.py`
- Test: `tests/test_merge_and_build.py`
- Test: `tests/test_calibre_html_publish.py`

- [ ] **Step 1: Copy the upstream pipeline files into `scripts/`**

Vendor the upstream versions from `deusyu/translate-book` without changing behavior yet.

- [ ] **Step 2: Copy or adapt the upstream tests into `tests/`**

Preserve existing test intent for:
- conversion helpers
- merge validation
- HTML publishing

- [ ] **Step 3: Adjust imports and paths for the new repo layout**

Ensure the vendored scripts import local modules correctly.

- [ ] **Step 4: Run the targeted tests**

Run: `pytest tests/test_convert.py tests/test_merge_and_build.py tests/test_calibre_html_publish.py -q`
Expected: all vendored pipeline tests pass or fail only due to missing external binaries that are clearly skipped or mocked.

- [ ] **Step 5: Commit**

```bash
git add scripts tests
git commit -m "feat: vendor conversion and build pipeline"
```

### Task 3: Add Stage-2 Ollama Draft Translation

**Files:**
- Create: `scripts/ollama_stage_translate.py`
- Modify: `SKILL.md`
- Test: `tests/test_ollama_stage_translate.py`

- [ ] **Step 1: Write the failing tests for draft-stage behavior**

Cover:
- finds `chunk*.md`
- skips chunks that already have `draft_`
- writes `draft_chunk*.md`
- respects a max-attempts value
- preserves source/output mapping

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `pytest tests/test_ollama_stage_translate.py -q`
Expected: failures for missing implementation.

- [ ] **Step 3: Implement `ollama_stage_translate.py`**

Core responsibilities:
- enumerate source chunks
- call local Ollama HTTP API for `aya-expanse:8b`
- save outputs as `draft_chunk*.md`
- retry failed chunks once
- support configurable parallelism defaulting to `1`

- [ ] **Step 4: Update `SKILL.md` with draft-stage invocation details**

Document:
- model name default
- output naming
- concurrency ceiling

- [ ] **Step 5: Run the tests again**

Run: `pytest tests/test_ollama_stage_translate.py -q`
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add SKILL.md scripts/ollama_stage_translate.py tests/test_ollama_stage_translate.py
git commit -m "feat: add ollama draft translation stage"
```

### Task 4: Add Stage-3 Ollama Refinement

**Files:**
- Create: `scripts/ollama_stage_refine.py`
- Modify: `SKILL.md`
- Test: `tests/test_ollama_stage_refine.py`

- [ ] **Step 1: Write the failing tests for refine-stage behavior**

Cover:
- reads source `chunk*.md`
- reads matching `draft_chunk*.md`
- writes `refined_chunk*.md`
- does not overwrite a better draft with a failed refine result
- retries once

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `pytest tests/test_ollama_stage_refine.py -q`
Expected: failures for missing implementation.

- [ ] **Step 3: Implement `ollama_stage_refine.py`**

Core responsibilities:
- pair source and draft files
- call local Ollama HTTP API for `gemma4:26b`
- enforce low-temperature, faithful-edit prompts
- reject empty or clearly degraded refine outputs

- [ ] **Step 4: Update `SKILL.md` with refinement-stage guidance**

Document:
- expected inputs
- refusal to summarize or restructure
- failure handling

- [ ] **Step 5: Run the tests again**

Run: `pytest tests/test_ollama_stage_refine.py -q`
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add SKILL.md scripts/ollama_stage_refine.py tests/test_ollama_stage_refine.py
git commit -m "feat: add ollama refinement stage"
```

### Task 5: Add Audit and Promotion Logic

**Files:**
- Create: `scripts/chunk_audit.py`
- Modify: `SKILL.md`
- Test: `tests/test_chunk_audit.py`

- [ ] **Step 1: Write the failing tests for audit behavior**

Cover:
- empty output detection
- suspiciously short output detection
- markdown mismatch heuristics
- residual English detection
- promotion of good `refined_` to `output_`

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `pytest tests/test_chunk_audit.py -q`
Expected: failures for missing implementation.

- [ ] **Step 3: Implement `chunk_audit.py`**

Core responsibilities:
- inspect `draft_`, `refined_`, `output_`
- classify chunks as pass, retry-stage-2, retry-stage-3, final-review-needed
- optionally promote clean `refined_` files to `output_`

- [ ] **Step 4: Update `SKILL.md` with audit and final-review rules**

Document:
- which chunks go to Codex final review
- that non-flagged refined chunks may be promoted automatically

- [ ] **Step 5: Run the tests again**

Run: `pytest tests/test_chunk_audit.py -q`
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add SKILL.md scripts/chunk_audit.py tests/test_chunk_audit.py
git commit -m "feat: add chunk audit and promotion stage"
```

### Task 6: Finalize the Codex Skill Workflow

**Files:**
- Modify: `SKILL.md`
- Modify: `agents/openai.yaml`
- Test: manual skill-read review

- [ ] **Step 1: Expand `SKILL.md` into the full user workflow**

Include:
- parameter collection
- stage ordering
- sample chunk rules
- local model stages
- final Codex review stage
- packaging instructions
- reporting requirements

- [ ] **Step 2: Validate that the skill text matches actual script names and outputs**

Check all filenames:
- `sample_chunk*.md`
- `draft_chunk*.md`
- `refined_chunk*.md`
- `output_chunk*.md`

- [ ] **Step 3: Refresh `agents/openai.yaml` if needed**

Ensure metadata matches the final skill behavior.

- [ ] **Step 4: Perform a consistency review**

Run: `rg -n "draft_|refined_|output_|aya-expanse|gemma4|pandoc|ebook-convert" SKILL.md agents/openai.yaml scripts tests`
Expected: names are internally consistent.

- [ ] **Step 5: Commit**

```bash
git add SKILL.md agents/openai.yaml
git commit -m "feat: finalize codex skill workflow"
```

### Task 7: End-to-End Dry Run on a Temp Book Directory

**Files:**
- Modify: `tests/` as needed
- Create: optional fixture files under `tests/fixtures/`
- Test: end-to-end dry run command sequence

- [ ] **Step 1: Prepare a small fixture or synthetic temp directory**

Include:
- a few `chunk*.md`
- `manifest.json`
- `config.txt`

- [ ] **Step 2: Run draft stage on the fixture**

Run: `python3 scripts/ollama_stage_translate.py --help`
Expected: CLI is available and documents required args.

- [ ] **Step 3: Run refine stage on the fixture**

Run: `python3 scripts/ollama_stage_refine.py --help`
Expected: CLI is available and documents required args.

- [ ] **Step 4: Run audit stage on the fixture**

Run: `python3 scripts/chunk_audit.py --help`
Expected: CLI is available and documents required args.

- [ ] **Step 5: Run the Python test suite**

Run: `pytest -q`
Expected: tests pass.

- [ ] **Step 6: Commit**

```bash
git add tests
git commit -m "test: cover end-to-end translation pipeline helpers"
```

### Task 8: Prepare Installation and Publishing Readiness

**Files:**
- Modify: `SKILL.md`
- Modify: `.gitignore`
- Test: git status and repository inspection

- [ ] **Step 1: Verify the repo is clean and self-contained**

Run: `git status --short`
Expected: only intended tracked files are present.

- [ ] **Step 2: Verify the remote is configured**

Run: `git remote -v`
Expected: `origin` points to the GitHub repository.

- [ ] **Step 3: Review the final file inventory**

Run: `find . -maxdepth 3 -type f | sort`
Expected: all skill, script, doc, and test files are present.

- [ ] **Step 4: Commit final polish if needed**

```bash
git add .
git commit -m "chore: prepare skill repository for publishing"
```
