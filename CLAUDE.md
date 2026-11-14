# Evidence Jam 2026, Lane 1: causal-claim extraction pipeline

Turn the 308 restoration articles in `corpus/*.md` into ONE merged CAMO v0.10.0 causal graph (`schema/causalmosaic.yaml`),
written as YAML and JSON, with an LLM (Qwen on the shared BRINE endpoint).

## Judging (what matters)
- One command: `./run.sh corpus/ output/` on a clean checkout (pinned deps, aarch64-safe). A failed run or ANY schema error
  halves the automatic score.
- Score = annotation quality first (accuracy floor), then energy per article (LLM tokens). Fewer tokens only matter once
  accuracy is good.
- Every `corpus/index.csv` row needs a `source_documents` entry (with its DOI); every edge's `source_document` must be one of them.
- The last commit before **Sun Nov 15, 6 p.m. EST** on the team repo (`team` remote) is judged. `origin` is the organisers' repo.

## Pipeline (`pipeline/`)
1 preprocess (`preprocess/`: clean, sections, sentences with raw-markdown offsets, citation filter, stats compression,
species legend, context) → 2 grounding (`grounding.py`, `data/terms.tsv`, `data/ncbitaxon_names.tsv`) → 3 LLM extraction
(`extract.py`, prompt `prompt/system.txt`, one line per claim `F|...`/`N|...`) → 4 parse + expand (`parse.py`, `expand.py`) →
5 guard + merge (`guard.py`) → 6 write + validate (`write.py`).
- `--preprocess paragraph-chunks` (default since 2026-11-14, see `reports/RESULTS.md`): the teammate's paragraph selection
  (`preprocess/team_paper.py`, verbatim; adapter `team_adapter.py`), one LLM call per paragraph chunk. `paragraph`: the same,
  whole paper in one call. `sentence`: our sentence filter. `sentence-chunks`: the sentence filter, one call per chunk.
- The LLM cache is `.cache/extract/` (key = model + prompt + input + max_tokens): an unchanged input never costs tokens twice.

## Commands
```
./run.sh corpus/ out/ [--docs A,B] [--preprocess sentence|paragraph|paragraph-chunks] [--prompt FILE] [--concurrency 8]
.venv/bin/python -m pytest -q tests                      # full suite, ~50 s (a hook runs the relevant fast subset after edits)
.venv/bin/python dev/eval_murphy.py --cached --others    # exact before/after on CACHED model output (post-processing changes)
.venv/bin/python dev/eval_murphy.py out/camo_graph.yaml --others     # score any graph on the gold papers
dev/compare_preprocess.sh --set all --reps 3 --variants "sentence paragraph-chunks"   # repeated endpoint runs + table
python dev/mock_endpoint.py 18999                        # fake endpoint for plumbing tests (scores from it mean nothing)
dev/preflight.sh                                         # clean-checkout submission check
```

## Evaluation protocol
- Gold: 5 papers in `dev/gold/` (`murphy2005.yaml` is the organisers' example and the primary yardstick; `4CB9X9XE`,
  `3KPITIV3`, `6HKWT4QG`, `ITXNQ843` are team annotations, used as an out-of-sample check). Every experiment, including its
  control, is evaluated on all 5 (`set=gold5`, `eval_murphy.py --others`); LOG entries before 2026-11-14 16:00 used 4 papers
  (no ITXNQ843), so do not compare their out-of-sample numbers with gold5 numbers. Report Murphy separately from the
  out-of-sample papers and say which a pooled (micro) number covers. Scorer: `dev/score/` (gated levels
  loose/standard/strict; standard = right entities + object attribute similarity >= 0.5).
- Post-processing changes (parse/expand/guard/write): exact comparison on cached model output, no noise.
- Prompt or preprocessing changes: endpoint runs are noisy (Murphy standard F1 varies about ±0.04 between identical runs),
  so use >= 3 repeats per variant and compare means and ranges.
- Every change must be justified for BOTH stage-1 models (sentence and paragraph-chunks); say so if it only helps one.
- Log every experiment in `dev/experiments/LOG.md` (use `/experiment`). Do not tune to the scorer's quirks; improve the extraction.

## Endpoint access
- `BRINE_URL`, `BRINE_MODEL`, `BRINE_API_KEY` come from the environment only. Claude's own shell usually does NOT have them.
- The user starts `tmux new -d -s jobs 'dev/jobrunner.sh'` in a shell that has them; Claude then queues runs by writing
  `dev/jobs/queue/NAME.job` (one line of key=value; NAME must be new). Keys: `preprocess=sentence|paragraph|paragraph-chunks
  prompt=<file> cache=on|refresh|off set=gold5|gold4|murphy|all thinking=on|off max_tokens=<1000-16000> refine=on|off
  samples=1|2|3` (refine=on / samples>1 only once the pipeline has `--refine` / `--samples`; checked per job, no restart).
  Up to 2 jobs run at once (oldest first); a bad key/value is REJECTED at once, a job the pipeline rejects FAILS, both with
  the reason in `dev/jobs/runner.log`; the runner keeps going. Output goes to `dev/jobs/out/NAME/`.
  Never edit `dev/jobrunner.sh` while it runs without telling the user to restart it (`tmux kill-session -t jobs`, not STOP).

## Hard rules
- NEVER write, print or commit the API key. Hooks block key-like strings in edits, commits and pushes.
- NEVER edit `dev/gold/`, `schema/`, `corpus/` or `data/camo.schema.json` (hook-enforced). Ask the user instead.
- Never modify `corpus/`; never weaken validation; the output must pass `linkml-validate -s schema/causalmosaic.yaml -C CausalGraph`.
- Commit or push only when the user asks; never force-push; run the full test suite before committing.
- Changes to `pipeline/` must keep `./run.sh` working from a clean checkout (`/preflight` before any submission push).
- Report results honestly: say when something was not run, and give ranges, not single runs, for endpoint results.
