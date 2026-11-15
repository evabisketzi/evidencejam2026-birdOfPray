# Results

State on 2026-11-15, 04:00 EST (after the overnight session). All numbers are from our own scorer (`dev/score/`) on the reference papers (five before 2026-11-15, eight since). They are
development numbers, not the judges' score.

## Submitted configuration

| setting | value |
|---|---|
| Preprocessing | `paragraph-chunks`: paragraph selection, one model call per chunk of at most 2,500 tokens |
| Prompt | `pipeline/prompt/system.txt` |
| Thinking | off |
| Output limit per call | 3,000 tokens |

## Overnight changes (2026-11-15) and their measured effect

All of these change only what happens after the model (parsing, node building, the guard). Each was checked exactly by
replaying the saved answers of several endpoint runs (`dev/replay.py`) on both preprocessing models and all eight
reference papers: Murphy (human), three development papers and four regression papers that were not tuned on
(`dev/eval8.py`, Claude references from `dev/annot_v2/`). Numbers are standard F1, mean over the runs.

| change | why | effect |
|---|---|---|
| Lenient claim-line parser | 17 % of the model's lines did not follow the format and were mostly lost (repair recovered 2 of 40 on the gold papers) | 4 answer sets per model: paragraph-chunks Murphy 0.571 → 0.576, development 0.125 → 0.142, regression 0.130 → 0.145; sentence 0.550 → 0.555, 0.084 → 0.099, 0.167 → 0.182; null recall up on both |
| Lines that start with their language letter (`A|5|...`) | 3.4 % of all lines were silently ignored | Murphy unchanged; regression set 0.148 → 0.169 (paragraph-chunks), 0.171 → 0.211 (sentence) |
| `measured_attribute` = the quality ("size" for "size of year 1 rosettes"), as the schema defines it | the bearer belongs to the entity; the node name keeps the whole phrase | Murphy: sentence 0.517 → 0.544, paragraph-chunks 0.597 → 0.583 (one set each); others unchanged |
| Species fan-out merged | the model spread "small trees" over all 15 species in the legend (846 edges in the full run) | 4C479SU8: 297 → 79 edges, F1 0.035 → 0.076; nothing else changed |
| Duplicate check keeps conditions | the same pair at another dose or season is a different claim | no change on the 8 papers |

The submitted configuration with this code, 3 endpoint runs on the eight reference papers (mean [range]):

| model | Murphy std F1 | Murphy strict F1 | Murphy null recall | development (3) std F1 | regression (4) std F1 | tokens per paper |
|---|---|---|---|---|---|---|
| **paragraph-chunks (submitted)** | 0.579 [0.575–0.583] | 0.518 | 0.711 | 0.169 [0.163–0.173] | 0.170 [0.166–0.172] | about 7,800 + 2,050 |
| sentence filter | 0.554 [0.544–0.573] | 0.490 | 0.667 | 0.111 [0.099–0.123] | 0.212 [0.208–0.215] | 5,693 + 1,493 |

Full run with this code (`full_new_1115`; same answers as the earlier full run, only repair calls were new): 308 papers,
0 failed, 30,208 edges (before: 27,429), JSON Schema + linkml-validate passed; unparseable lines 2,263 → 223; tokens per
paper 9,308 + 2,263 (before: 10,110 + 2,493, because fewer repair calls are needed).

Tried and not adopted (2 endpoint runs per model each, details in the log): prompts that list every outcome
(`x_enum`, `x_enum2`) or forbid species lists for groups (`x_grp`); keeping every Results paragraph (`--keep-results`);
`--taxon-groups`; a legend without generic common names (`--clean-variants`); larger chunks (`--chunk-tokens 4000`, 14 %
fewer tokens but lower accuracy everywhere). None gave a consistent gain on both models; Murphy varies 0.542–0.583 between
identical paragraph-chunks runs.

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
  comes from 4CB9X9XE (0.174 against 0.068). Against the cleaned annotations the lead is smaller (0.156 against 0.139).
- **Cost:** paragraph-chunks uses about 25 % more tokens per paper on these five papers. Over all 308 papers its input
  is about 8 % larger (1.82 million tokens against 1.68 million, counted offline). We accept this because accuracy is
  scored before energy.
- **Prompt:** `system_v1.txt` halves Murphy standard F1 on both models, so `system.txt` stays.

## What is not measured

- **Full-corpus runs:** paragraph-chunks ran on all 308 papers on 2026-11-14/15 (`full_pc_1114`, 4.7 h, 0 failures), and
  again with the overnight code from the same answers (`full_new_1115`). There is no gold for the other 300 papers.
- **Absolute accuracy outside Murphy is low** for every variant (standard F1 below 0.1, loose F1 about 0.2).
- **The gold set is small, and only Murphy is a human annotation.** Five papers, three runs per variant. The four
  out-of-sample annotations (4CB9X9XE, 3KPITIV3, 6HKWT4QG, ITXNQ843) were made by Claude. Part of the low out-of-sample
  score came from how those files word their entities, not from wrong claims: against cleaned copies
  (`dev/annot_v2/`, same pipeline output) the out-of-sample standard F1 is 0.156 [0.151–0.162] for paragraph-chunks and
  0.139 [0.125–0.150] for the sentence filter, and loose F1 is about 0.30 for both.

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
| `--keep-results` | Paragraph selection keeps every Results prose paragraph (tested 2026-11-15: worse). |
| `--clean-variants` | Species legend without generic "common names" such as "species" or "trees" (tested: inconsistent). |
| `--chunk-tokens N` | Paragraph text per model call (default 2,500; 4,000 tested: 14 % fewer tokens, lower accuracy). |

## Earlier reports

- `reports/overnight_REPORT.md`: the full-corpus run of 2026-11-13 and the first prompt comparison.
- `reports/preprocess_COMPARE.md`: the first sentence-filter against paragraph-selection comparison (two gold papers).
