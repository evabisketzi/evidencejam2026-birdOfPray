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

| variant | Murphy standard F1 | Murphy strict F1 | Murphy loose F1 | Murphy null recall | Out-of-sample standard F1 | Out-of-sample loose F1 | Tokens per paper (in + out) |
|---|---|---|---|---|---|---|---|
| **paragraph-chunks, `system.txt` (submitted)** | 0.570 [0.559–0.591] | 0.506 [0.500–0.515] | 0.781 [0.773–0.794] | 0.644 [0.600–0.667] | 0.069 [0.066–0.075] | 0.191 [0.185–0.202] | 8,312 + 2,277 |
| sentence filter, `system.txt` | 0.563 [0.550–0.569] | 0.494 [0.483–0.500] | 0.847 [0.846–0.847] | 0.600 [0.600–0.600] | 0.032 [0.031–0.034] | 0.176 [0.170–0.180] | 6,319 + 2,181 |
| paragraph-chunks, previous paragraph code | 0.541 [0.507–0.569] | 0.484 [0.451–0.511] | 0.775 [0.746–0.803] | 0.622 [0.600–0.667] | 0.066 [0.064–0.068] | 0.215 [0.197–0.235] | 8,325 + 2,292 |
| sentence filter, prompt `system_v1.txt` | 0.284 [0.257–0.324] | 0.256 [0.200–0.324] | 0.791 [0.743–0.831] | 0.111 [0.000–0.333] | 0.034 [0.034–0.035] | 0.067 [0.063–0.075] | 7,169 + 2,217 |
| paragraph-chunks, prompt `system_v1.txt` | 0.279 [0.247–0.307] | 0.265 [0.233–0.292] | 0.849 [0.836–0.876] | 0.400 [0.333–0.467] | 0.036 [0.034–0.039] | 0.113 [0.110–0.115] | 9,213 + 2,324 |

Per-run numbers for every paper are in `reports/results/batch0_scores.json`.

What the table shows:

- **Murphy:** paragraph-chunks and the sentence filter are tied. The difference (0.570 against 0.563) is smaller than
  the difference between identical runs (about ±0.04).
- **Out-of-sample:** paragraph-chunks is about twice as good at the standard level (0.069 against 0.032). Most of that
  comes from 4CB9X9XE (0.174 against 0.068).
- **Cost:** paragraph-chunks uses about 25 % more tokens per paper on these five papers. Over all 308 papers its input
  is about 8 % larger (1.82 million tokens against 1.68 million, counted offline). We accept this because accuracy is
  scored before energy.
- **Prompt:** `system_v1.txt` halves Murphy standard F1 on both models, so `system.txt` stays.

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

## Earlier reports

- `reports/overnight_REPORT.md`: the full-corpus run of 2026-11-13 and the first prompt comparison.
- `reports/preprocess_COMPARE.md`: the first sentence-filter against paragraph-selection comparison (two gold papers).
