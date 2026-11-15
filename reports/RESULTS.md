# Results

State on 2026-11-14, evening. All numbers are from our own scorer (`dev/score/`) on five gold papers. They are
development numbers, not the judges' score.

## Submitted configuration

| setting | value |
|---|---|
| Preprocessing | `paragraph-chunks`: paragraph selection, one model call per chunk of at most 2,500 tokens |
| Prompt | `pipeline/prompt/system.txt` |
| Thinking | off |
| Output limit per call | 3,000 tokens |

## Why this configuration

Three endpoint runs per variant on the five gold papers, cache bypassed. Values are the mean, with the lowest and
highest run in brackets. "Out-of-sample" is the mean over the four team-annotated papers (4CB9X9XE, 3KPITIV3,
6HKWT4QG, ITXNQ843).

| variant | runs | Murphy std F1 | Murphy std P | Murphy std R | Murphy strict F1 | Murphy loose F1 | Murphy null recall | Out-of-sample std F1 | Out-of-sample std P | Out-of-sample std R | Out-of-sample loose F1 | Tokens per paper (in + out) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **paragraph-chunks, `system.txt` (submitted)** | 3 | 0.570 [0.559–0.591] | 0.609 [0.582–0.650] | 0.537 [0.528–0.542] | 0.506 [0.500–0.515] | 0.781 [0.773–0.794] | 0.644 [0.600–0.667] | 0.069 [0.066–0.075] | 0.071 [0.066–0.078] | 0.071 [0.069–0.074] | 0.191 [0.185–0.202] | 8,312 + 2,277 |
| sentence filter, `system.txt` | 3 | 0.563 [0.550–0.569] | 0.557 [0.532–0.569] | 0.569 [0.569–0.569] | 0.494 [0.483–0.500] | 0.847 [0.846–0.847] | 0.600 [0.600–0.600] | 0.032 [0.031–0.034] | 0.031 [0.029–0.032] | 0.036 [0.033–0.039] | 0.176 [0.170–0.180] | 6,319 + 2,181 |
| paragraph-chunks, previous paragraph code | 3 | 0.541 [0.507–0.569] | 0.560 [0.514–0.600] | 0.523 [0.500–0.542] | 0.484 [0.451–0.511] | 0.775 [0.746–0.803] | 0.622 [0.600–0.667] | 0.066 [0.064–0.068] | 0.065 [0.060–0.067] | 0.069 [0.068–0.069] | 0.215 [0.197–0.235] | 8,325 + 2,292 |
| sentence filter, prompt `system_v1.txt` | 3 | 0.284 [0.257–0.324] | 0.285 [0.263–0.329] | 0.282 [0.250–0.319] | 0.256 [0.200–0.324] | 0.791 [0.743–0.831] | 0.111 [0.000–0.333] | 0.034 [0.034–0.035] | 0.034 [0.032–0.035] | 0.036 [0.036–0.036] | 0.067 [0.063–0.075] | 7,169 + 2,217 |
| paragraph-chunks, prompt `system_v1.txt` | 3 | 0.279 [0.247–0.307] | 0.285 [0.243–0.323] | 0.273 [0.250–0.292] | 0.265 [0.233–0.292] | 0.849 [0.836–0.876] | 0.400 [0.333–0.467] | 0.036 [0.034–0.039] | 0.030 [0.028–0.032] | 0.046 [0.044–0.049] | 0.113 [0.110–0.115] | 9,213 + 2,324 |
| camo_pipeline (reference: JSON extraction + study call + gleaning; one saved run) | 1 | 0.467 | 0.714 | 0.347 | 0.467 | 0.579 | 0.267 | 0.084 | 0.098 | 0.075 | 0.397 | 15,961 + 5,588 |

Per-run numbers for every paper are in `reports/results/batch0_scores.json` (camo reference: `reports/results/reference_scores.json`).
The table is generated: `python dev/results_table.py table reports/results/batch0_scores.json reports/results/reference_scores.json --labels reports/results/variant_labels.csv` (new runs: `python dev/results_table.py score FILE.json NAME_r1=GRAPH.yaml`).

What the table shows:

- **Murphy:** paragraph-chunks and the sentence filter are tied. The difference (0.570 against 0.563) is smaller than
  the difference between identical runs (about ±0.04).
- **Out-of-sample:** paragraph-chunks is about twice as good at the standard level (0.069 against 0.032). Most of that
  comes from 4CB9X9XE (0.174 against 0.068).
- **Cost:** paragraph-chunks uses about 25 % more tokens per paper on these five papers. Over all 308 papers its input
  is about 8 % larger (1.82 million tokens against 1.68 million, counted offline). We accept this because accuracy is
  scored before energy.
- **Prompt:** `system_v1.txt` halves Murphy standard F1 on both models, so `system.txt` stays.
- **Precision and recall** (columns added 2026-11-14 night, from the same per-run files): out of sample, the submitted
  configuration is equally weak on both (P 0.071, R 0.071). On Murphy it is the most precise of our variants (P 0.609).
- **camo_pipeline reference** (one saved run of the research pipeline, scored with the same scorer): lower on Murphy
  (0.467; null recall 0.267) but higher out of sample (standard 0.084, **loose 0.397 against 0.191**), at about twice the
  tokens. It finds the right pair of entities about twice as often outside Murphy; what it does differently is analysed in
  the section on the merge branch below. One run only: the noise between identical runs is about ±0.04.

## What is not measured

- **No full-corpus endpoint run of the submitted configuration yet.** The only full run so far (2026-11-13) used the
  sentence filter: 308 papers processed, 22,938 edges, 23,840 nodes, schema-valid. For paragraph-chunks, all 308
  papers pass preprocessing offline and the whole pipeline passes against a mock endpoint, but the real endpoint has
  only seen the five gold papers.
- **Absolute accuracy outside Murphy is low** for every variant (standard F1 below 0.1, loose F1 about 0.2).
- **The gold set is small.** Five papers, three runs per variant. Three of the four out-of-sample annotations
  (3KPITIV3, 6HKWT4QG, ITXNQ843) are noted in our diagnostics as machine-assisted and have not been confirmed as
  human-checked; Murphy and 4CB9X9XE are human annotations.

## Changes made on 2026-11-14 and their measured effect

Exact comparisons on cached model output unless stated otherwise. Full entries are in `dev/experiments/LOG.md`.

| change | effect | kept |
|---|---|---|
| Hedged sentences are labelled "uncertain" instead of "direct" | Murphy F1 unchanged; language mix closer to the gold on every paper | yes |
| Node-name fixes | F1 unchanged; 141 "presence of an action" names removed over 308 papers | yes |
| Results-section detection fixes | 6 papers that had no results sentences now have them; +1.5 % input tokens | yes |
| Paper-defined abbreviations written out in node names | F1 unchanged; pure-abbreviation names 148 → 87 | yes |
| "pH" kept lower-case | F1 unchanged | yes |
| A claim repeated in the same sentence is kept once | Murphy standard F1 0.593 → 0.602 (sentence), 0.535 → 0.543 (paragraph-chunks); 130 edges dropped over 308 papers | yes |
| Updated paragraph preprocessing (3 endpoint runs) | Murphy 0.541 → 0.570, inside the noise | yes |
| Prompt `system_v1.txt` (3 endpoint runs per model) | Murphy 0.56 → 0.28 | no |

## Options that exist but are off by default

These are implemented and tested, change nothing unless switched on, and are still being measured:

| flag | idea |
|---|---|
| `--taxon-groups` | Group words such as "rodents" or "grasses" get the group's NCBITaxon ID (`data/taxon_groups.tsv`, IDs checked against NCBI Taxonomy). |
| `--preprocess sentence-chunks` | The sentence filter with one model call per chunk. |
| `--cite-filter relaxed` | Keeps discussion sentences that cite a source but state the authors' own interpretation. |
| `--retry-underextraction` | Retries a paper once when it yields fewer than 0.15 claims per sentence. |
| `--prompt system_lang.txt` | A prompt variant for the direct / hedged / associational distinction. |

## Merge branch `merge_camo_onto`: camo_pipeline ideas and the ontology module (2026-11-14, night)

Based on `main` at 250b105. Two sources are merged in, every change as a pipeline flag that is **off by default**:

- **`camo_pipeline/`**, the research pipeline (JSON extraction, study-facts call, gleaning, code-side fitting). Its code is
  reference material only; nothing runs from it. See the camo reference row above for how it scores.
- **`ontology/`** (Eva's `ontologies_p_script` branch, newest version from `harness`). The LLM never writes an ID: code
  looks names up in committed ELMO / ENVO / GO / PATO / ChEBI / PO / UBERON indexes, writes an ID only for a unique exact
  match, and lets the model pick among candidates by number for the rest (see `ontology/GROUNDING.md`). Until now nothing
  in `pipeline/` called it.

| flag | what it does | from | cost |
|---|---|---|---|
| `--ontology lookup` | IDs for unique exact matches (`--ontology-fields entities`: not for `measured_attribute`); a blocklist of generic words (`quality` would become PATO's root term) | `ontology/ground_terms.py`, camo `ontology.py` BLOCKED | none |
| `--ontology select` | as lookup, plus one short call per paper for the ambiguous / fuzzy terms; decisions remembered in `ontology/ontology_index/selection_memo.json` | `ontology/select_terms.py` | ~1 short call per paper |
| `--fit-attributes` | life-stage words leave the attribute (`seedling number` = `number of individuals` + seedling; `rosette` also as `life_stage_term`), a leading direction word goes to the qualifier | camo `fit.fit_attribute` | none |
| `--double-negative` | `prevents` + a `decreased` object becomes `causes` + decreased | camo `fit.fit_finding` R1 | none |
| `--provenance` | `annotator` (`camo_agent:<model>`), `annotation_timestamp`, node `variable_key` | camo `assemble.py` | none |
| `--study` | one short call on the CONTEXT block: `study_design`, `study_country`, `study_state_or_province`, `study_period_*`, `study_duration_months` on `source_documents`; `evidence_types` from the design | camo `prompts.STUDY_*` | ~1 short call per paper |
| `--continue-truncated` | a reply cut off at `--max-tokens` gets one more call with the sentences after the last one it cited (34 of 308 papers hit the cap in the full run). Cut-offs are now counted in `run_log.json` in every mode | camo `run.py` `truncated_rest` | only on cut-off chunks |
| `--glean auto` | one extra call per paper on abstract / results / discussion sentences that no claim cites and that carry `[sig]` / `[ns]` or a result word (at least 3, at most ~2,300 tokens) | camo `run.glean_candidates` | ~1 call per paper |

The job runner accepts them as keys (`ontology=`, `ontology_fields=`, `glean=`, `study=`, `continue=`, `fit_attributes=`,
`double_negative=`, `provenance=`) and `set=gold8` (gold5 + the three papers added on `harness`).

### Measured offline (no endpoint, no extraction cache on this machine)

- **Nothing changes with the flags off.** The 8 gold papers through the team mock endpoint (`dev/mock_endpoint.py`): the
  graph is byte-identical to `main`'s (JSON and YAML; only `provenance.created` differs). With every flag on, the graph
  passes JSON Schema and linkml-validate.
- **Tests:** 312 pass (`PYTHONUTF8=1 pytest -q` on Windows; the UTF-8 switch is needed there for one existing test
  that reads linkml output, not on Linux). This includes the 6 tests of `ontology/tests/test_grounding.py`
  (gold precision 1.0, 47 of 47).
- **Ontology lookup on real model output** (camo's saved graphs, the same edges with and without IDs):

  | | Murphy std F1 | Out-of-sample std F1 | values changed |
  |---|---:|---:|---:|
  | camo reference, no IDs added | 0.467 | 0.084 | — |
  | `lookup`, entities only | 0.467 | 0.078 | 2 |
  | `lookup`, all fields | 0.467 | 0.073 | 42 |

  The drop with entities only is one 4CB9X9XE gold edge. It is a **scorer artefact**: when `entity_term` is an ID,
  `dev/score` compares the node *name* instead, and has labels only for NCBITaxon and a few attribute IDs, not for
  ELMO / ENVO / GO. So the F1 cost of ontology IDs here is a limit of our yardstick, not proof of worse annotations.
- **How much the gold uses ontologies** (`dev/diag/ontology_coverage.py`): ENVO for 40–60 % of environmental variables
  (3KPITIV3, 6HKWT4QG, ITXNQ843), GO for processes, PATO for only about 8 % of measured attributes. This supports
  grounding `entity_term` and keeping most attributes as text (`--ontology-fields entities`).
- On camo's output, lookup alone adds IDs to +6 % of all values (+14 % of attributes). Another 20 % are candidates for
  `select`.

### Not measured yet: needs the endpoint (or the full-run extraction cache)

Exact checks on cached output, no tokens (on the machine that holds `.cache/extract/`):

```
EVAL_PREPROCESS=paragraph-chunks EVAL_FEATURES=fit-attributes python dev/eval_murphy.py --cached --others --prompts system.txt
EVAL_PREPROCESS=paragraph-chunks EVAL_FEATURES=double-negative python dev/eval_murphy.py --cached --others --prompts system.txt
EVAL_PREPROCESS=paragraph-chunks EVAL_ONTOLOGY=lookup:entities python dev/eval_murphy.py --cached --others --prompts system.txt
```

Endpoint arms, 3 repeats each against a control in the same code state (job files for `dev/jobrunner.sh`):

```
preprocess=paragraph-chunks set=gold5 cache=refresh study=on            # tokens and how many source_documents get a design
preprocess=paragraph-chunks set=gold5 cache=refresh glean=auto          # recall / null recall vs precision, tokens
preprocess=paragraph-chunks set=gold5 cache=refresh continue=on         # against max_tokens=8000 (QUEUE batch 2)
preprocess=paragraph-chunks set=gold5 cache=refresh ontology=select     # coverage (dev/diag/ontology_coverage.py) and F1
```

Then `dev/diag/camo_vs_main_entities.py dev/diag/out/camo_ref.yaml <run>/camo_graph.yaml` shows, gold edge by gold
edge, how camo words the entities it finds and the submitted pipeline misses: that decides the one port not built yet
(entity wording; it has to be narrow, because `system_v1.txt`, "entities in the paper's words", halved Murphy F1).

## Earlier reports

- `reports/overnight_REPORT.md`: the full-corpus run of 2026-11-13 and the first prompt comparison.
- `reports/preprocess_COMPARE.md`: the first sentence-filter against paragraph-selection comparison (two gold papers).
