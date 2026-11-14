# Experiment queue (2026-11-14 evening → overnight → Sun Nov 15, 6 p.m. EST snapshot)

Rules for this queue:
- Every experiment is evaluated on gold5 (YKQQZV93, 4CB9X9XE, 3KPITIV3, 6HKWT4QG, ITXNQ843), 3 repeats per arm,
  against a control run on the SAME code state. Murphy reported separately; pooled numbers say what they cover.
- The runner runs whatever code is on disk when a job starts. So every code change below is a pipeline FLAG, default
  off, switched on per job by a runner key. Prompt variants are separate prompt files. One code state per batch.
- Endpoint speed today: 11-15 min per gold5 job, 2 in parallel → about 6.5 min per job of wall time.
- 3 of the 5 gold papers (3KPITIV3, 6HKWT4QG, ITXNQ843) are labelled "Claude silver" in dev/diag/13_preproc_three.md:
  confirm who made them. If silver, weigh Murphy and 4CB9X9XE (human) higher.

## Batch 0: running now (ends about 17:30)
| arm | jobs | control | decides |
|---|---|---|---|
| teammate's preprocess_paper.py update (paragraph-chunks) | tp_new_pc ×3 | tp_ctrl_pc ×3 (old code) | keep / revert team_paper.py |
| prompt system_v1.txt (entities in the paper's words) | v1_sf ×3, v1_pc ×3 | ctrl_sf ×3; tp_new_pc ×3 (same new preprocessing) | best prompt P* = system.txt or system_v1.txt |

## Offline work during batch 0 (no runner)
1. Flags (default off, existing modes byte-identical; checked on all 308 papers):
   - `--preprocess sentence-chunks`: our sentence filter, one call per ~2,500-token chunk split at section boundaries,
     header repeated (team_adapter chunk_texts path). Check: sentences identical to `--preprocess sentence`.
   - `--cite-filter relaxed`: keep a discussion sentence with an own-study cue ("our", "we", "this study") even if it
     cites. Check with dev/diag/d13_preproc_three.py: visibility up, Murphy loses nothing; token change over 308 papers;
     sample of restored sentences read by hand. Affects the sentence modes only.
   - `--taxon-groups`: group words (rodents, small mammals, trees, conifers, grasses, forbs, shrubs, mosses, fish,
     salmonids, amphibians ...) get a SPECIES legend entry with the group's NCBITaxon ID from a hand-built
     data/taxon_groups.tsv (verified IDs only; e.g. Rodentia NCBITaxon:9989 as in the 4CB9X9XE gold), resolved by
     grounding.taxon_id(). Report gold nodes whose group ID would now match.
   - `--retry-underextraction`: retry once (cache bypassed) when claims per sentence fall below a threshold chosen from
     dev/overnight/20261113_202118/full_baseline/run_log.json (2F76GVEE: 8 edges vs 76); keep the result with more
     valid claims; mock-endpoint test; report how many of 308 papers would trigger it.
2. Prompt draft for causal language / predicate (from P*, both candidates prepared, the right one picked at 17:30):
   observational comparison or co-occurrence → a (cw with a statistic) + A; only an experimental manipulation with an
   unhedged causal verb → D; "likely"/"probably" stay D (Murphy gold) → remove "likely" from the U list.
3. Runner: new validated keys, passed only when the pipeline has the flag (no further restart needed later):
   `preprocess=sentence-chunks`, `cite_filter=strict|relaxed`, `taxon_groups=on|off`, `retry=on|off`.

## Decision point D0 (about 17:30)
- Verdicts for batch 0 → P*. Commit kept changes (ask first). Merge the fan-out limit (exactly gold-neutral).
- USER: restart the runner once (new keys). Commands in CLAUDE.md / the session.

## Batch 1 (about 17:35-19:15, 15 jobs): all arms vs P* from batch 0 (same code state)
| arm | jobs | measures |
|---|---|---|
| (2) causal language + predicate prompt | sf ×3, pc ×3 | predicate + language accuracy on matched pairs, language-mix distance (dev/diag/lang_dist.py), F1 |
| (1) group-level taxa (`taxon_groups=on`) | sf ×3, pc ×3 | F1 per paper, gold nodes matched by group ID |
| sentence-chunks (`preprocess=sentence-chunks`) | ×3 | F1, null recall, tokens vs sentence and paragraph-chunks |
(1) and (2) run in parallel as asked; the combination is checked in batch 3.

## Batch 2 (about 19:15-20:15, 9 jobs)
| arm | jobs | note |
|---|---|---|
| cited-background filter (`cite_filter=relaxed`) | sf ×3 (+ sentence-chunks ×3 if kept) | paragraph models unaffected (inputs checked identical) |
| `max_tokens=8000` | sf ×3, pc ×3 | 34 of 308 papers hit the 3,000 cap in the full run; the cache key changes, note it in the LOG |

## Batch 3 (about 20:15-21:15): combination
All kept changes together, 3 repeats per candidate stage-1 model (sentence / sentence-chunks / paragraph-chunks).
Choose THE submission configuration (stage-1 model + prompt + flags turned into defaults).

## Overnight (from about 21:30; 2 slots ≈ 19 slot-hours until 7 a.m.)
Queued in this order (the runner takes the oldest job first):
| # | job(s) | est. slot time | decided by |
|---|---|---|---|
| 1 | full corpus run of the chosen configuration (`set=all`, incl. the under-extraction retry if it passed offline) | ~3.5-4 h (last full run: 21:01-00:27) | safety-net submission graph |
| 2 | prompt (a) one effect per listed trait ("large leaves, flowers, fruits" → 3 effects): sf ×3, pc ×3 | ~1.2 h | USER in the morning |
| 3 | prompt (b) null-result wording → N line ("did not differ/vary", "no significant", "similar", "no additional benefit", "were consistent across", "remained unchanged"): sf ×3, pc ×3 | ~1.2 h | USER in the morning |
| 4 | P* with `thinking=on max_tokens=16000`: sf ×3, pc ×3 | ~3-5 h (thinking is slower; not measured yet) | USER in the morning |
Then `dev/preflight.sh --full` on the commit of job 1. Expected end: about 3-5 a.m.
- (a) and (b) are written from P* after batch 3 (about 21:15), each as its own prompt file; the control is P* from batch 3.
- Evidence: (a) 11 of 22 never-found Murphy gold edges come from listed traits (dev/diag/7_never_found.md);
  (b) 21-36 missed edges are null mismatches, null recall 0 on 3KPITIV3 and 6HKWT4QG.
- Cache key includes thinking and max_tokens: thinking runs never mix with non-thinking answers.
- Time risk: if (a), (b) or thinking is kept in the morning, the submission needs a NEW full run (~3.5-4 h without
  thinking; with thinking possibly 10+ h, which would not finish before 6 p.m. unless started by about 4 a.m.).
  So the morning decision must be made by about 11 a.m. for a non-thinking change.

While the overnight jobs run (no runner, in a worktree; nothing merged into main until the morning):
- /experiment verified attribute IDs for data/terms.tsv from the Lane 2 graph
  (github.com/timalamenciak/evidencejam2026-lane2, causal_graph.json, embedding_text) and ../envo-environment-CURIE.json:
  verified pairs only (reject e.g. presence -> PATO:0000070 "amount"); exact check on cached output for both models;
  report nodes gaining an ID. Kept or reverted by the experiment rules, merged only after the overnight runs.
- Score every overnight batch as it finishes and write the numbers into dev/experiments/LOG.md as PENDING (no decision
  on (a), (b) or thinking until the user is back).
- The Claude session must stay open overnight (it is woken by the job notifications).

## Sunday morning
1. USER: decide (a), (b), thinking (by about 11 a.m. if a new full run is needed).
2. If needed: new full run of the final configuration (~3.5-4 h), then `dev/preflight.sh --full`.
3. Commit; USER: merge into the submission branch and push to `team` before 6 p.m.

## Do not forget (smaller, can slot in anywhere)
- Two source spans for sentences the new team code rejoins across a caption (346 corpus sentences).
- Name actions consistently: "Herbicide spraying", not "Occurrence of herbicide spraying" (_ACTION_NOUN list).
- Scorer: long gold entity_term on ITXNQ843 (141 items): USER decision; do not chase it in the prompt.
- Branches: today's commits are on main only; harness / paragraph-chunks / team main need a decision (USER).
- Uncommitted: gold5 runner + CLAUDE.md + skill edits; system_v1.txt + test; fan-out worktree branch exp-fanout.
