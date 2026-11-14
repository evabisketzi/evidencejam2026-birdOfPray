---
name: experiment
description: Run ONE controlled pipeline experiment - make a single change, evaluate it against the Murphy 2005 gold (plus the other gold papers) for both stage-1 models, keep or revert it, and log the result. Use when the user asks to try, test or evaluate a change to the prompt, preprocessing, expansion, grounding or guard.
argument-hint: "<the change to try>"
---

# /experiment — one change, measured, kept or reverted, logged

Change to test: **$ARGUMENTS**

Follow these steps in order. One change per experiment: if the request contains several, do the first and propose the rest.

## 1. Baseline and starting state
- `git status --short`: start from a clean working tree for the files you will touch (commit or note pre-existing changes;
  never stash blindly).
- Read the latest numbers in `dev/experiments/LOG.md` (reference table + last KEPT entry). These are the baseline only if
  they were measured on all 5 gold papers (gold5: YKQQZV93, 4CB9X9XE, 3KPITIV3, 6HKWT4QG, ITXNQ843). Entries before
  2026-11-14 16:00 used 4 papers: then run the step-4 commands as the control BEFORE the edit (post-processing: the cached
  eval, which scores all 5; input-changing: control jobs with `set=gold5`) and record those numbers.
- State the hypothesis in one sentence: what should improve, on which metric, and why (cite the evidence: a score file, a
  failure list, a diag file).

## 2. Classify the change (decides how it is measured)
- **Post-processing** — `pipeline/parse.py`, `expand.py`, `guard.py`, `grounding.py`, `write.py`, `data/terms.tsv`: the model's
  lines do not change, so measure EXACTLY on cached output (no endpoint, no noise).
- **Input-changing** — `pipeline/prompt/*`, `pipeline/preprocess/*`, legend/context, chunking, `max_tokens`: the model sees new
  input, so it needs endpoint runs (noisy: Murphy standard F1 moves about ±0.04 between identical runs).

## 3. Make the change
Edit the code. The PostToolUse hook runs the matching fast tests; fix any failure before evaluating. Add or update a unit
test that pins the new behaviour. Never touch `dev/gold/`, `schema/`, `corpus/`.

## 4. Evaluate — BOTH stage-1 models
**Post-processing:**
```
.venv/bin/python dev/eval_murphy.py --cached --others --prompts system.txt                     # sentence model
EVAL_PREPROCESS=paragraph-chunks .venv/bin/python dev/eval_murphy.py --cached --others --prompts system.txt
```
(The paragraph-chunks line needs its cache: if it fails with a connection error, queue
`preprocess=paragraph-chunks prompt=system.txt cache=on set=gold5` once — see below.) If the LOG has no exact baseline for
this configuration, run these commands BEFORE making the edit (step 3) and record the numbers.

**Input-changing:** needs the job runner (`tmux ls` shows `jobs`; if not, give the user the start command from CLAUDE.md and
stop). Queue 3 repeats per model, cache bypassed but stored:
```
echo "preprocess=sentence prompt=system.txt cache=refresh set=gold5" > dev/jobs/queue/<exp>_sf_r1.job     # r1..r3
echo "preprocess=paragraph-chunks prompt=system.txt cache=refresh set=gold5" > dev/jobs/queue/<exp>_pc_r1.job
```
For a new prompt, save it as a new file in `pipeline/prompt/` and pass `prompt=<file>`; keep `system.txt` as the control.
Wait for `DONE` lines in `dev/jobs/runner.log` (use a background wait, do not poll), then score each:
`.venv/bin/python dev/eval_murphy.py dev/jobs/out/<name>/camo_graph.yaml --others`. Compare means and min–max to the control
runs (run the control in the same session if the LOG's control is older than the current code).

Also check the token cost (`dev/jobs/out/<name>/tokens.csv`): energy per article is scored.

## 5. Decide
KEEP only if all hold:
- Murphy standard F1 is not lower (post-processing: exactly; endpoint: mean not below the control mean − 0.01, and the target
  metric moved by more than the run-to-run range).
- The out-of-sample papers do not get worse on balance.
- There is a reason it should help BOTH the sentence and the paragraph-chunks model (if it only helps one, say which and why).
- It does not raise tokens without a matching accuracy gain.
Otherwise REVERT: `git checkout -- <changed files>` (only the files this experiment changed) and remove any new prompt file.
A neutral change that clearly improves output quality judges will read (names, grounding) may be kept; say so explicitly.

## 6. Log
Append an entry to `dev/experiments/LOG.md` in the existing format: date — title — KEPT/REVERTED; Change; Why (evidence);
Type; Result per model with numbers (before → after, ranges for endpoint runs); rejected variants; tests. If KEPT, run the
full suite (`.venv/bin/python -m pytest -q tests`) and, if the user has allowed commits, commit with message
`experiment: <title>`. Never push from this skill.

## 7. Report
Tell the user in a few lines: the change, the numbers for both models, the decision and why, and the next suggested experiment.
