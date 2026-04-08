# Gemma Glossary Fine-Tuning Feasibility Design

Date: `2026-04-08`

## Status

This document is a feasibility design only.

It does not commit the project to implementation now.
It exists to support a later decision, when the current translation pipeline is closer to completion and the team can judge whether glossary-aware fine-tuning is worth the extra complexity.

## Goal

Evaluate whether a glossary-aware fine-tuning path for local Gemma models is likely to be worth pursuing as a future enhancement to the current translation workflow.

The target outcome is not "replace the glossary database" or "remove audit."
The target outcome is narrower:

- make Stage 2 draft translation use preferred terminology more reliably
- reduce avoidable `term_mismatch` cases before audit
- improve adherence to `zh-TW` lexical preferences during drafting
- preserve the current retrieval-and-QA architecture instead of replacing it

## Current Baseline

The current translation pipeline is:

`convert -> sample -> draft -> refine -> audit -> merge/build`

Relevant behavior today:

- Stage 2 uses `gemma-4-e4b-it-mxfp8`
- Stage 3 uses `gemma-4-26b-a4b-it-mxfp4`
- NAER-backed glossary retrieval injects chunk-level terminology references into Stage 2 and Stage 3 prompts
- `chunk_audit.py` can flag `term_mismatch` cases after translation
- regional lexicon normalization remains a separate audit-stage concern

Current interpretation:

- glossary retrieval is already the main precision mechanism
- audit is already the main safety net
- model fine-tuning, if added later, should act as a compliance and consistency booster

## Decision Question

The project should not ask:

- "Can Gemma memorize 200,000 terms?"

The project should ask:

- "Can Gemma be tuned so that, when glossary references are present, it follows them more reliably and uses better terminology under realistic chunk-level context?"

This is the central design assumption of this document.

## Recommended Direction

Primary recommendation:

- `retrieval-first + medium/heavy LoRA`

Meaning:

- keep glossary retrieval as the authoritative source of terminology
- keep audit as the enforcement and QA layer
- use fine-tuning only to improve how the model behaves in the presence of glossary evidence and translation context

This makes fine-tuning a behavioral optimization problem, not a dictionary-storage problem.

## Compared Approaches

### Approach 1: Retrieval-First + Small LoRA

Model focus:

- primarily `gemma-4-e4b-it-mxfp8`

Intent:

- teach Stage 2 to follow glossary blocks more consistently
- improve `zh-TW` drafting habits
- keep training cost and iteration time relatively low

Strengths:

- cheapest to iterate
- easiest to re-run when training data improves
- lower operational risk

Limits:

- weaker contextual disambiguation
- less likely to fix harder terminology conflicts inside long narrative chunks
- may improve compliance without improving deeper translation judgment

### Approach 2: Retrieval-First + Medium/Heavy LoRA

Model focus:

- `gemma-4-e4b-it-mxfp8` as the fast candidate
- `gemma-4-26b-a4b-it-mxfp4` as the heavier candidate

Intent:

- keep retrieval authoritative
- improve term adoption during Stage 2
- evaluate whether a stronger model learns better contextual terminology use and more stable `zh-TW` rendering

Strengths:

- best balance between realism and expected payoff
- allows direct comparison between cheaper and stronger Gemma variants
- aligns with the current pipeline rather than trying to replace it

Limits:

- requires better training data than a simple term list
- increases experiment cost and evaluation burden
- 26B may improve quality, but the gain over E4B is not guaranteed

### Approach 3: Large-Scale Terminology-Centric Fine-Tuning

Model focus:

- whichever Gemma variant scales best in practice

Intent:

- turn glossary assets into a major training corpus and expect the model to internalize terminology preferences broadly

Strengths:

- highest theoretical upside if data quality is excellent

Limits:

- highest data engineering burden
- easiest way to spend a lot of effort for unstable gains
- most likely to confuse raw term recall with true chunk-level term selection
- highest risk of hurting general translation quality while chasing terminology coverage

Conclusion:

- Approach 2 is the correct future evaluation target
- Approach 1 should remain the lower-risk fallback
- Approach 3 should not be the default plan unless earlier experiments show unusually strong returns

## Why Raw Glossary Volume Is Not The Core Metric

The expected glossary footprint may approach 200,000 entries if imported broadly.

That number sounds large, but it is not the real decision variable.

Problems with treating raw entry count as the training objective:

- many entries are domain-specific and low-frequency
- many entries are ambiguous across domains
- some entries have multiple acceptable targets
- some entries matter only under local sentence or paragraph context
- a term list by itself does not teach the model when to trust or ignore a candidate mapping

Therefore:

- the real training asset is not the term table alone
- the real training asset is `source context + glossary evidence + target translation`

## Training Objective

The proposed training objective is:

- given a source chunk or excerpt
- given a glossary block or equivalent retrieved term context
- produce a translation that uses the preferred terminology when appropriate

The model should learn:

- glossary blocks are high-priority evidence
- preferred targets should usually win over generic alternatives
- `zh-TW` wording should be preferred where the project policy requires it
- terminology corrections should be local, not excuses to rewrite entire chunks

The model should not be expected to:

- replace the glossary database
- guarantee hard terminology compliance by parameter memory alone
- eliminate the need for audit

## Data Design

Three data layers are recommended.

### Layer 1: Glossary Assets

Source:

- imported NAER datasets
- project-maintained normalization rules
- future name/place datasets if adopted

Purpose:

- authoritative terminology inventory
- retrieval source during inference
- metadata source for sampling training examples

This layer is not enough by itself for fine-tuning.

### Layer 2: Training Examples

Preferred sample shape:

- `source_text`
- `glossary_block`
- `target_text`
- optional metadata:
  - dataset
  - domain
  - confidence
  - ambiguity type
  - whether the example is narrative, expository, or technical

Recommended example types:

- high-confidence direct terminology use
- ambiguous terms resolved by local context
- cases where only some glossary hits should be used
- `zh-CN` to `zh-TW` lexical preference cases that should survive draft generation
- negative or contrastive examples where a tempting but wrong rendering should not be chosen

Good sources for future sample generation:

- accepted final `output_chunk*.md`
- manually corrected high-risk chunks
- curated sentence- or paragraph-level examples derived from glossary hits
- selected audit failures paired with corrected outputs

### Layer 3: Evaluation Sets

Split into at least:

- terminology-heavy technical material
- narrative nonfiction with technical vocabulary
- glossary-rich but ambiguity-heavy chunks
- control set with low glossary density

Purpose:

- measure terminology gain
- measure regression in ordinary translation quality
- prevent success from being defined only by easy technical snippets

## Dataset Construction Strategy

Do not start from all glossary rows equally.

Instead, build the first experiment around a high-value subset.

Recommended ordering:

1. high-confidence, high-frequency, low-ambiguity terminology
2. medium-frequency terminology that appears in real translated books
3. ambiguity-heavy terms only after the pipeline for evaluation is stable

Practical first experiment:

- begin with roughly `2,000` to `10,000` high-value terms
- derive one to three contextual examples per term where possible
- prefer real book contexts over synthetic isolated sentences

Reasoning:

- this is enough to test whether the approach changes model behavior
- it avoids committing to a large data-engineering project before evidence exists

## Model Comparison: E4B vs 26B

### `gemma-4-e4b-it-mxfp8`

Best suited for:

- Stage 2 draft enhancement
- faster iteration loops
- early proof-of-value experiments

Expected advantages:

- cheaper and faster to tune
- closer to the current draft-stage runtime target
- easier to retrain when glossary policies evolve

Expected weaknesses:

- may plateau earlier on subtle contextual term decisions
- may improve compliance less on long or complex chunks

### `gemma-4-26b-a4b-it-mxfp4`

Best suited for:

- stronger context-sensitive terminology behavior
- harder ambiguity resolution
- higher-value final candidate if experiments justify it

Expected advantages:

- more room for context-sensitive gains
- potentially better at choosing the right term under narrative or mixed-domain context

Expected weaknesses:

- higher training and validation cost
- longer iteration cycle
- may still be unnecessary if E4B captures most of the practical gain

### Comparison Hypothesis

The most likely outcomes are:

- E4B delivers noticeable terminology-compliance gains per unit cost
- 26B delivers smaller but potentially important gains on ambiguous or mixed-context chunks
- the final decision should depend on whether 26B materially outperforms E4B on the project's hardest real-book cases

This means the future evaluation should not ask which model is "best" in general.
It should ask which model is best for the incremental value over the current retrieval baseline.

## Training Stack

Future implementation should prefer parameter-efficient tuning:

- `LoRA` or `QLoRA`

Rationale:

- lower implementation risk
- lower retraining cost when terminology data expands
- easier comparison across E4B and 26B
- easier rollback if the tuned model regresses

This document intentionally avoids locking the project to one trainer or framework now.
The future implementation can choose the specific stack based on the best-supported Gemma tooling at that time.

## Inference Architecture After Fine-Tuning

Even if tuning succeeds, inference should remain retrieval-first.

Proposed future behavior:

- Stage 2 continues to retrieve chunk-level glossary hits
- the tuned model receives glossary guidance in the prompt
- the tuned model is expected to follow the guidance more reliably than the untuned baseline
- audit still checks `term_mismatch`
- audit remains the place for hard evidence that the tuning is worth keeping

This preserves a clean separation of concerns:

- glossary DB: authoritative terminology source
- tuned model: better user of that source
- audit: verification and regression detection

## Evaluation Criteria

Future evaluation should succeed only if it improves both terminology behavior and overall translation usefulness.

Primary metrics:

- reduction in `term_mismatch` counts
- improvement in term-level precision on matched glossary hits
- reduction in avoidable `zh-CN` lexical drift inside Stage 2 drafts
- reduction in chunks escalated for terminology-related manual review

Secondary metrics:

- unchanged or improved readability on control chunks
- unchanged or improved structure preservation
- no meaningful increase in hallucinated terminology substitutions

Decision rule:

- do not adopt a tuned model if it only improves a narrow benchmark set
- do not adopt a tuned model if it harms general translation quality on ordinary chunks

## Cost Estimate

Only rough decision-level cost matters for now.

### Data Cost

Moderate to high.

Most of the real cost is not GPU time.
It is:

- extracting good contextual examples
- curating corrected targets
- separating high-confidence and ambiguous cases
- building evaluation sets that reflect real project risks

### Experiment Cost

`E4B`:

- relatively affordable for repeated LoRA-style experiments
- appropriate for early feasibility testing

`26B`:

- materially more expensive in compute and iteration time
- still acceptable if the team later decides that terminology consistency is strategically important and infrequent retraining is acceptable

### Maintenance Cost

Likely acceptable if:

- glossary updates remain infrequent
- retraining is occasional rather than continuous
- new entries can still be covered immediately by retrieval and audit before the next tuning cycle

This is an important point in favor of the approach.
Because glossary changes are not frequent, the project does not need a high-frequency fine-tuning pipeline to justify the idea.

## Risks

- the tuned model may look better on curated terminology tests but not on real books
- the tuned model may become overconfident and force glossary terms where they do not belong
- gains may come mostly from easier high-frequency terms, leaving hard ambiguity unsolved
- the data-engineering burden may exceed the actual quality gain
- 26B may cost more without delivering enough incremental benefit over E4B

## Decision Gate For Future Work

Do not begin implementation unless all of the following are true:

- the current glossary retrieval and audit pipeline is considered stable enough to serve as a baseline
- the project has a meaningful pool of corrected outputs suitable for training and evaluation
- the team can define a real acceptance threshold, not just "sounds better"
- the team is willing to keep retrieval and audit even after tuning

## Recommendation

Future recommendation, if this work is pursued:

1. keep retrieval-first architecture unchanged
2. run a first feasibility experiment on `gemma-4-e4b-it-mxfp8` with parameter-efficient tuning
3. evaluate against real-book chunks using the current glossary and audit metrics
4. only if E4B shows meaningful gains, run the same evaluation on `gemma-4-26b-a4b-it-mxfp4`
5. adopt a tuned model only if gains are clear on real pipeline outputs, not just curated examples

## Non-Goals

- replacing the glossary SQLite store
- removing glossary prompt injection
- removing audit
- promising immediate implementation
- promising that full glossary import alone will make tuning effective

## Summary Judgment

This idea is technically plausible and strategically reasonable enough to keep as a future enhancement candidate.

However, it is only worth doing under a retrieval-first design.
The likely winning version is not "train Gemma on 200,000 terms."
The likely winning version is:

- keep retrieval
- keep audit
- train Gemma to use retrieved terminology better
- prove value on real translated chunks before adopting it
