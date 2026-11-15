# Handoff (updated 2026-11-15 ~05:55 EST, overnight session; LOG.md entries from "2026-11-14 (night)" on)

Read this first in a new session. Then CLAUDE.md, then the last entries of dev/experiments/LOG.md.

## State: ready to commit (nothing committed or pushed — the user decides)
- The working tree holds tonight's post-processing fixes (all default ON, all measured by exact replay on several answer
  sets, both models, 8 reference papers): lenient parser, A|/U|/D| lines, measured_attribute head, species fan-out merge,
  condition-aware duplicate check. Plus run telemetry (raw_responses.jsonl, losses.jsonl) and new off-by-default flags
  (--keep-results, --clean-variants, --chunk-tokens, all tested and rejected).
- `full_new_1115` = the submitted configuration with this code over all 308 papers: 0 failed, 30,208 edges, JSON Schema +
  linkml-validate passed (dev/jobs/out/full_new_1115/). Tests: 281 passed.
- reports/METHOD.md and reports/RESULTS.md are updated (also the earlier uncommitted RESULTS fix about 4CB9X9XE).

## To submit (user)
1. Review the diff (`git diff`, untracked: dev/replay.py, dev/eval8.py, dev/show_io.py, dev/cached8.py, tests/test_replay.py,
   dev/annot_fix.py, dev/annot_v2/, data/2F76GVEE.yaml, data/4C479SU8.yaml, data/V3H4MP29.yaml, tests/test_annot_fix.py).
2. The experiment prompts are archived under dev/experiments/prompts_overnight/ (fine to commit or to leave out).
3. Full tests, commit, `/preflight`, push to `team` before Sun 6 p.m. EST.

## Finished since 04:00
- thinking=on: rejected (every call used the 12,000-token cap without output; no edges).
- Third baseline run per model: final numbers in RESULTS.md (paragraph-chunks Murphy 0.579 [0.575–0.583], dev3 0.169,
  reg4 0.170). Nothing is queued; the job runner is idle.
- The x_* experiment prompts were moved to dev/experiments/prompts_overnight/ (pipeline/prompt/ is clean again).

## Endpoint access without the user
- Claude's shell has no BRINE variables. Runs go only through the tmux `jobs` runner (never stop it unattended).
  Extra flags: `pipeline/prompt/x_NAME.txt` (+ `x_NAME.txt.args`, e.g. `--docs <8 papers> --clean-variants`).

## Open ideas (not done)
- Remaining 128 dropped lines in the full run are mostly garbled (T1/T2/T3/..., glued lines); not worth more rules.
- Input-side changes (prompt, selection, legend) move single papers a lot in both directions; any further one needs
  >= 3 runs per model.
