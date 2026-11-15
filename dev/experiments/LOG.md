# Experiment log

One entry per change, newest last. Written by `/experiment` (or by hand in the same format).
Primary yardstick: Murphy 2005 (`dev/gold/murphy2005.yaml`). Out-of-sample check: 4CB9X9XE, 3KPITIV3, 6HKWT4QG.
Metrics: standard / strict / loose F1, null recall, causal-language accuracy on matched pairs (`dev/eval_murphy.py`).

## Reference numbers (before the 2026-11-14 changes)
| model | how measured | Murphy std F1 | strict | null recall | 4-paper micro std F1 |
|---|---|---:|---:|---:|---:|
| sentence filter, system.txt | cached full-run output (exact) | 0.593 | 0.504 | 0.467 | — |
| sentence filter, system.txt | 3 endpoint runs, mean (range) | 0.548 (0.524–0.593) | 0.478 | 0.533 | 0.189 (0.185–0.195) |
| paragraph-chunks, system.txt | cached job `pc_base` (exact) | 0.535 | 0.465 | 0.733 | — |
| paragraph-chunks, system.txt | 3 endpoint runs, mean (range) | 0.564 (0.514–0.613) | 0.502 | 0.667 | 0.215 (0.194–0.226) |

Causal-language mix (all 4 gold papers, cached sentence-filter output): ours D/U/A/N = 55/30/11/5 %; gold is far less
direct (Murphy 33/39/11/17, 4CB9X9XE 2/48/31/19, 3KPITIV3 20/17/59/4, 6HKWT4QG 23/35/35/7).

---

## 2026-11-14 — causal-language calibration (hedged sentences)  — KEPT
- **Change:** `pipeline/expand.py` `calibrate_language()`: `direct_causal` on a sentence with may/might/could/would/appears/
  seems/suggests → `uncertain_causal`.
- **Why:** the model labels 55–61 % of edges direct vs 21 % in the gold; on Murphy the matched disagreements were mostly hedged
  sentences ("It appears that…", "The results suggest…").
- **Type:** post-processing → exact check on cached output.
- **Result (sentence model):** Murphy std F1 0.593 → 0.593, causal-language accuracy 0.700 → 0.700 (unchanged); mean distance of
  the language mix from the gold over 4 papers 0.37 → 0.34 (better on every paper).
- **Rejected variants:** broad hedge list (likely, probably, indicated, generally …): Murphy language accuracy 0.70 → 0.50 (the
  Murphy annotator keeps "likely killed", "indicated" direct). Downgrading every observational-design edge: distance 0.37 → 0.41
  (the gold uses *associational* there, not uncertain; that needs the prompt).
- **Paragraph-chunks model** (cached job `pc_base`, before = commit 6ffec9d on the same cached output): Murphy std F1 0.535 →
  0.535; 4CB9X9XE causal-language accuracy 0.400 → 0.500; language-mix distance from gold 0.27 → 0.24. Its raw output is
  already less "direct" than the sentence model's (Murphy distance 0.06).
- **Tests:** `tests/test_pipeline.py::test_calibrate_language_hedges_only`.

## 2026-11-14 — node-name template fixes  — KEPT
- **Change:** `pipeline/expand.py` `compose_name()`: an action is named by itself ("Establishment of X", not "Presence of
  establishment of X"); no "Removal of … closure"; no repeated taxon; a value in the property slot reads "natural ecotone type";
  an adjective as the thing reads "herbaceous species richness".
- **Why:** readability for judges and downstream lanes; gold names actions this way ("transplanting of Sanguinaria canadensis").
- **Type:** post-processing → exact check.
- **Result:** Murphy std F1 0.593 → 0.593 (unchanged; Socratic 0.421 → 0.421). Re-expanding all 308 cached papers: action-as-
  presence 141 → 0, double action 4 → 0, repeated taxon 2 → 0, adjective-as-thing 2 → 0 (17 borderline cases remain).
- **Paragraph-chunks model:** same code path; Murphy std F1 0.535 → 0.535, other papers unchanged.
- **Tests:** `test_entity_type_defaults_when_no_type_code_is_given` updated ("Mowing" instead of "Occurrence of mowing").

## 2026-11-14 — results-section detection fixes  — KEPT
- **Change:** `pipeline/preprocess/sections.py`: (1) the fuzzy `ref` rule matched any heading containing "reference",
  including "pre*ference*s" ("Herbivore Forage Preferences", "Host preference of EM fungi"), "Reference sites" and "Shifting
  reference condition", which sent results/discussion into the dropped reference list; it now needs the heading to start or end
  with references / literature cited / bibliograph* / works cited. (2) exact headings are retried without a parenthetical
  ("Results (interim results for …)"). (3) `_results_after_analysis`: with Methods and Discussion but no Results heading, the
  subheadings after the last statistics/analysis subsection of Methods become Results (fallback `results_after_analysis`).
  (4) a fuzzy Conclusions heading ("2.1.2 Implications") is ignored before Results (exposed by (1) in thesis MPWDHPDB).
- **Why:** `dev/diag/11_no_results_section.txt`: 9 papers had 0 `res` sentences; heading dumps showed the causes above.
- **Type:** preprocessing (input-changing), but measured exactly offline: pre.txt of all 308 papers × both stage-1 models
  before/after.
- **Result:** gold papers (YKQQZV93, 4CB9X9XE, 3KPITIV3, 6HKWT4QG) byte-identical for BOTH models → gold scores unchanged by
  construction (same cache key; no endpoint runs needed or made). Res sentences before → after: 3YNFB29I 0→36, 4RFTRJCP 0→29,
  6DBK8P4E 0→39, ANWITZVF 0→21, ECK26ZFG 0→8, R7HU9C7W 0→126 (+30 dis, +15 con; thesis), C5H5V7NH/FLNPSPIG/XJ7ET7G6 0→0
  (report, short communication, framework: intentionally untouched). Collateral recoveries from the "preference" bug:
  DLHT9LI3 res 52→109, IDBWDU97 14→151, GGD3VPZ4 19→26, R9QX7FQG dis 15→39; 6 others differ only in captions/legend.
  Sentence-model input tokens 1,659,884 → 1,684,187 (+1.5 %, all in the 16 changed papers).
- **Paragraph-chunks model:** paragraph selection unchanged; only the SPECIES legend / CONTEXT line differ in 10 papers
  (built from our section detection); input tokens 1,822,308 → 1,822,681.
- **Not measured:** extraction quality on the changed papers (no gold for them); output-token change needs a full run.
- **Rejected variant:** squashed-key `startswith("references")` (matched "Reference sites"); `bibliography` without `\w*`
  (lost the French "Bibliographie" of EKQPGZD6, leaking its source list into `con`).
- **Tests:** `tests/test_sections.py`: `test_parenthetical_heading_and_reference_subheadings`,
  `test_results_subsections_after_reference_subheading_are_kept`, `test_topic_headings_after_data_analysis_become_results`;
  full suite 253 passed.

## 2026-11-14 — paper-defined abbreviations expanded in node names  — KEPT (neutral on gold; readability)
- **Change:** new `pipeline/preprocess/abbrev.py`: Schwartz-Hearst detection of "long form (ABBR)" / "(ABBR, unit)"
  definitions over the whole cleaned paper, stored in the sidecar as `abbreviations` (never shown to the model: pre.txt
  unchanged). `pipeline/expand.py`: node names are composed from the model's own words, then each defined abbreviation is
  expanded once, keeping it in brackets ("Soil VMC" -> "Soil volumetric moisture content (VMC)"); `measured_attribute` is
  expanded too (grounding tries the expanded, then the original attribute). No expansion inside brackets or when the long
  form is already written. Sentence-initial capitals dropped ("acid mine drainage"), names kept ("Sørensen's ..."), plural
  definitions singularised ("(GHGs)" -> greenhouse gas).
- **Why:** pure-abbreviation node names ("NEP", "AMD", "Occurrence of MLTT") are unreadable for judges and downstream lanes.
- **Type:** post-processing → exact check on cached output.
- **Result (sentence model):** Murphy std F1 0.593 → 0.593; 4CB9X9XE / 3KPITIV3 / 6HKWT4QG identical (no defined abbreviation
  reaches a gold-paper node). Corpus (all 308 cached papers, `dev/diag/abbrev_names.py sentence --head-sections`):
  1,691 definitions found; pure-abbreviation names 148 → 87 (remaining: undefined chemical symbols "Soil P", "NH4-N", "PH"
  (= pH capitalised by `_cap`), "GEPmax"); 655 names changed in 111 papers. Random sample of 45 changed names: ~40 correct
  and clearer, the rest odd but not wrong (e.g. "BLM-TU" with a long paper definition).
- **Paragraph-chunks model:** same expand code and the same sidecar (the adapter copies it); Murphy std F1 0.535 → 0.535,
  other gold papers identical. Corpus count not possible: only the 4 gold papers are cached for this model.
- **Rejected variants:** expanding before composing the name (changed template branches: "FMM cover soil type" -> "Floor
  mineral mix (FMM) of cover soil type"); naive plural stripping ("greenhouse gase").
- **Tests:** `tests/test_abbrev.py` (3 tests); full suite 256 passed.

## 2026-11-14 — keep "pH" lower-case in node names  — KEPT
- **Change:** `pipeline/expand.py` `_cap()`: a name starting with a mixed-case term ("pH", "eDNA", "mRNA") is not capitalised.
- **Why:** 6 node names in the full run read "PH" (the remaining pure-abbreviation names after the expansion experiment).
- **Type:** post-processing → exact check.
- **Result:** Murphy std F1 0.593 → 0.593 (sentence), 0.535 → 0.535 (paragraph-chunks); other gold papers identical.
- **Tests:** `tests/test_abbrev.py::test_cap_keeps_mixed_case_terms`.

## 2026-11-14 — drop a claim repeated within the same sentence  — KEPT
- **Change:** `pipeline/guard.py` `integrity()` + `same_sentence_key()`: an edge with the same subject node, predicate, object
  node, null flag, mediators and cited sentence(s) as an earlier edge of the paper is dropped (first one kept). The same
  claim from different sentences is kept (the gold repeats claims that way).
- **Why:** d12 (`dev/diag/d12_failure_budget.py`): duplicate rate 15 % (sentence) / 9 % (paragraph-chunks) vs 8 % in the gold;
  same-sentence repeats are pure model repetition.
- **Type:** post-processing → exact check on cached output ("before" = same code with the key made unique per edge).
- **Result (sentence model):** Murphy std F1 0.593 → 0.602, strict 0.504 → 0.511, P 0.635 → 0.656, loose 0.770 → 0.752
  (2 edges dropped; both exact copies of a kept edge; each had been loose-matched to a DIFFERENT gold edge from another
  sentence, i.e. never a real match); 4CB9X9XE / 3KPITIV3 / 6HKWT4QG identical. d12 duplicates on the 4 gold papers
  34/232 (15 %) → 32/230 (14 %).
- **Paragraph-chunks model:** Murphy std F1 0.535 → 0.543, strict 0.465 → 0.471, loose 0.746 → 0.729 (same reason);
  other gold papers identical; d12 duplicates 21/236 (9 %) → 19/234 (8 %).
- **Corpus (full_baseline graph, 308 papers):** 130 edges dropped in 41 papers (R9DVQAQB 26, IBH9XBA8 21, 4RFTRJCP 11);
  d12 duplicates 3208/22938 (14.0 %) → 3078/22808 (13.5 %). Most d12 "duplicates" are cross-sentence repeats, kept on purpose.
- **Rejected variant:** keying on the scorer's normalised token sets (205 instead of 130 drops): it merges different claims
  ("→ Diversity" and "→ Species richness" share a token after normalisation), i.e. tuning to a scorer quirk.
- **Tests:** `tests/test_pipeline.py::test_guard_drops_a_claim_repeated_in_the_same_sentence_but_keeps_other_sentences`.

## 2026-11-14 — teammate's preprocess_paper.py update (team/main 9b5f13c) in `team_paper.py`  — KEPT (neutral within noise; stays in step with the team)
- **Change:** `pipeline/preprocess/team_paper.py` replaced by the teammate's updated file (paragraph modes only).
- **Why:** keep the paragraph models on the team's current preprocessing; offline visibility check in `dev/diag/13_preproc_three.md`.
- **Type:** input-changing → 3 endpoint runs per arm, gold5, `cache=refresh` (jobs `tp_ctrl_pc_r1-3` old code, `tp_new_pc_r1-3` new code).
- **Result (paragraph-chunks model), mean [range]:** Murphy std F1 0.541 [0.507–0.569] → 0.570 [0.559–0.591], strict 0.484 → 0.506,
  loose 0.775 → 0.781, null recall 0.622 → 0.644 (all inside the ±0.04 run-to-run noise). Out-of-sample (mean of 4CB9X9XE,
  3KPITIV3, 6HKWT4QG, ITXNQ843): std F1 0.066 [0.064–0.068] → 0.069 [0.066–0.075]; loose 0.215 [0.197–0.235] → 0.191 [0.185–0.202],
  the drop coming from 6HKWT4QG (loose 0.508 → 0.377; its std F1 0.063 → 0.074). Tokens per paper 8,325+2,292 → 8,312+2,277.
- **Sentence model:** not affected (does not use `team_paper.py`).
- **Not measured:** the other 303 papers (no gold).

## 2026-11-14 — prompt `system_v1.txt` (entities in the paper's words)  — REVERTED (not adopted; P* stays `system.txt`)
- **Change:** prompt variant `pipeline/prompt/system_v1.txt`.
- **Type:** input-changing → 3 endpoint runs per arm, gold5, `cache=refresh`. Controls on the same code state: `ctrl_sf_r1-3`
  (sentence), `tp_new_pc_r1-3` (paragraph-chunks).
- **Result (sentence model), mean [range]:** Murphy std F1 0.563 [0.550–0.569] → 0.284 [0.257–0.324], strict 0.494 → 0.256,
  loose 0.847 → 0.791, null recall 0.600 → 0.111; out-of-sample (mean of 4) std F1 0.032 → 0.034, loose 0.176 → 0.067.
  Tokens per paper 6,319+2,181 → 7,169+2,217.
- **Result (paragraph-chunks model):** Murphy std F1 0.570 [0.559–0.591] → 0.279 [0.247–0.307], strict 0.506 → 0.265,
  loose 0.781 → 0.849, null recall 0.644 → 0.400; out-of-sample std F1 0.069 → 0.036, loose 0.191 → 0.113.
  Tokens per paper 8,312+2,277 → 9,213+2,324. Two of the three runs took 22–25 min (usually about 11).
- **Reading:** entities are still found (Murphy loose F1 holds) but no longer match at the standard level, on both models,
  far outside the noise. The causal-language accuracy on matched pairs was higher (0.70 / 0.76 vs 0.675 / 0.621), on far fewer pairs.
- **Left in place:** the file `system_v1.txt` and its test are still in the working tree, unused (not deleted without the user's say).

## 2026-11-14 (night) — branch `merge_camo_onto`: camo_pipeline ports + the ontology module, all as flags  — PENDING (default off)
- **Change:** new flags, all default off: `--ontology off|lookup|select` + `--ontology-fields all|entities`
  (`pipeline/ontology_stage.py`, wraps Eva's `ontology/` from `harness` unchanged), `--fit-attributes`, `--double-negative`,
  `--provenance` (`pipeline/features.py`), `--study` (`pipeline/study.py`), `--continue-truncated` and `--glean off|auto|always`
  (`pipeline/extract.py`). Job runner keys for each, and `set=gold8`. `dev/eval_murphy.py --cached` takes
  `EVAL_FEATURES=...` and `EVAL_ONTOLOGY=lookup[:entities]`. Report tooling: `dev/results_table.py` (generates the RESULTS.md
  table from per-run score files, now with P and R), `dev/diag/merge_graphs.py`, `dev/diag/ontology_coverage.py`,
  `dev/diag/camo_vs_main_entities.py`.
- **Why:** camo_pipeline (one saved run, same scorer) is lower on Murphy (0.467 vs 0.570) but higher out of sample (std 0.084 vs
  0.069, loose 0.397 vs 0.191); the ontology module existed but nothing called it.
- **Type:** mixed. `--fit-attributes`, `--double-negative`, `--provenance`, `--ontology lookup` are post-processing → exact check on
  cached output. `--study`, `--glean`, `--continue-truncated`, `--ontology select` add calls → endpoint arms.
- **Checked:** flags off, the 8 gold papers through `dev/mock_endpoint.py`: graph byte-identical to `main` (JSON and YAML, except
  `provenance.created`). Every flag on: JSON Schema + linkml-validate pass. Per-paper extra prompt tokens on the mock (meaningless
  for F1): study + ontology select ≈ +1k; gleaning +3-4k at the first cap, so the cap was lowered to ~2,300 tokens.
- **Result (ontology lookup, exact, on camo's saved graphs):** Murphy std F1 0.467 → 0.467 (both modes); out-of-sample std F1
  0.084 → 0.078 (`entities`, 2 values changed) / 0.073 (`all`, 42 values). The `entities` drop is one 4CB9X9XE edge and a scorer
  artefact: with an ID in `entity_term` the scorer compares the node name (no ELMO/ENVO/GO labels). Gold practice
  (`dev/diag/ontology_coverage.py`): ENVO on 40-60 % of environmental variables, PATO on ~8 % of attributes.
- **Rejected variants:** PATO for every attribute without a blocklist: `quality` → PATO:0000001 (PATO's root), `competition` →
  ELMO "competition intensity" (both listed under Known limitations in `ontology/GROUNDING.md`) → blocklist in the stage.
- **Pending:** the exact checks on the extraction cache and the endpoint arms listed in `reports/RESULTS.md` (section on this
  branch). Decide per flag by the queue rules (beat the control by more than the noise, or F1-neutral and valid).
- **Tests:** `tests/test_ontology_stage.py`, `test_features.py`, `test_study.py`, `test_truncation.py`, `test_glean.py`.
