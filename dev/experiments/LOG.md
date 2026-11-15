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

## 2026-11-14 — prompt `system_lang.txt` (causal language and predicate)  — REVERTED (not adopted; prompt stays `system.txt`)
- **Change:** prompt variant: a manipulated treatment or explicit causal verb (also with likely/probably) = D; hedged = U;
  an observed difference or co-occurrence without manipulation or causal verb = A with predicate a.
- **Type:** input-changing → 3 endpoint runs per arm, gold5, `cache=refresh` (`lang_sf_r1-3`, `lang_pc_r1-3`); controls
  `ctrl_sf_r1-3`, `tp_new_pc_r1-3` on the same code state. Out-of-sample numbers below use the ORIGINAL annotations.
- **Result (sentence model), mean [range]:** Murphy std F1 0.563 [0.550–0.569] → 0.550 [0.534–0.579]; causal-language
  accuracy 0.675 → 0.708 [0.692–0.718]; predicate accuracy 0.805 → 0.791; out-of-sample std F1 0.032 → 0.040, loose 0.176 → 0.212.
  Tokens per paper 6,319+2,181 → 6,574+2,191.
- **Result (paragraph-chunks model):** Murphy std F1 0.570 [0.559–0.591] → 0.544 [0.493–0.585]; causal-language accuracy
  0.621 → 0.592 [0.529–0.658]; null recall 0.644 → 0.511 [0.267–0.667]; out-of-sample std F1 0.069 → 0.047, loose 0.191 → 0.166.
- **Reading:** a small language gain on the sentence model (about the size of the run-to-run range), a loss on the
  submitted paragraph-chunks model. Fails the "both models" rule.
- **Not run:** the other batch-1 arms (`taxon_groups=on`, `preprocess=sentence-chunks`): they need the runner restarted
  with the new keys.

## 2026-11-14 — cleaned copies of the machine-made annotations (`dev/annot_v2/`)  — evaluation data, not a pipeline change
- **Fact (user, 2026-11-14):** only Murphy 2005 is human-annotated; 4CB9X9XE, 3KPITIV3, 6HKWT4QG, ITXNQ843 (and
  2F76GVEE, 4C479SU8, V3H4MP29 in `data/`) were made by Claude.
- **Change:** `dev/annot_fix.py` writes cleaned copies to `dev/annot_v2/` (originals untouched): character offsets for
  1,190 spans, 9 species names → NCBITaxon IDs, method detail in brackets removed from terms, 38 hand edits
  (`term_edits.tsv`) that reduce over-specified terms to the entity. No claim added, removed or re-judged. All 7 files
  pass linkml-validate. Details and every change: `dev/annot_v2/README.md`, `CHANGES.md`.
- **Why:** on ITXNQ843 the pipeline and the annotation state nearly the same claims, yet loose F1 was about 0.05, because
  every annotated subject carried method detail ("broadcast glyphosate application without species targeting").
- **Effect on scores (same pipeline output, mean of the 4 out-of-sample papers, 3 runs):** sentence std F1 0.032 → 0.134
  [0.120–0.145], loose 0.176 → 0.304; paragraph-chunks std F1 0.069 → 0.153 [0.148–0.158], loose 0.191 → 0.298.
  ITXNQ843 loose 0.05–0.07 → 0.45–0.51; 4CB9X9XE unchanged. Murphy is not affected.
- **Claim review (same day):** all 209 edges of the four gold5 files read against their sentences. 4CB9X9XE and 6HKWT4QG:
  nothing changed. 3KPITIV3: 4 edges now quote the sentence that supports them (three light-ring edges quoted the one
  sentence that contradicts the paper's own finding). ITXNQ843: 4 null results that were only in the annotation notes
  are edges now (55 → 59). No predicate, language or direction was found wrong. Not covered: claims in sentences the
  annotation never quotes; the three further papers. Out-of-sample null recall on the cleaned files: sentence 0.000 in
  all 3 runs, paragraph-chunks 0.273.
- **Cited-study claims removed (user decision, same day):** Murphy annotates none (25 findings, all the study's own), so
  11 edges whose claim is reported from another study were deleted (3KPITIV3 1, 6HKWT4QG 5, ITXNQ843 5). Final edge counts
  48 / 45 / 55 / 54. Final scores on the cleaned files (same control runs): sentence std F1 0.139 [0.125–0.150], loose 0.310
  [0.307–0.314]; paragraph-chunks std F1 0.156 [0.151–0.162], loose 0.301 [0.294–0.311]. These supersede the figures above.
- **Use:** `EVAL_OTHERS_DIR=dev/annot_v2 .venv/bin/python dev/eval_murphy.py GRAPH --others`. `dev/gold/` still holds the
  originals (hook-protected). Numbers on the cleaned files are not comparable with earlier out-of-sample numbers.
- **What the remaining gap shows:** 3KPITIV3: the pipeline writes "blue rings" as a free-text variable where the annotation
  uses the species plus an attribute; 4CB9X9XE: "rodent density" as a variable where the annotation uses the Rodentia ID
  (the unmeasured `--taxon-groups` flag targets this).

## 2026-11-14 (night) — tooling for unattended work: saved answers, replay, prompt sidecar, eight-paper scorer  — infrastructure
- **Why:** Claude's shell has no BRINE variables; the only endpoint access is the running job runner (fixed keys, cannot be
  restarted unattended). The cache keeps one answer per input, so downstream changes could only be checked on ONE response set.
- **Change:** every run writes `raw_responses.jsonl` (all answers in call order) and `losses.jsonl` (every claim line lost before
  the graph: unparseable after/without repair, unknown sentence numbers, failed papers). `dev/replay.py JOB OUT.yaml` replays
  a run's answers through the current code (checked exact: identical edges and nodes on a mock run). `pipeline/prompt/<p>.args`
  adds command-line flags for experiment prompts (later args win, so `--docs` overrides the job's set); `system.txt` has none.
  `dev/eval8.py` scores Murphy (human) / dev3 (4CB9X9XE, 3KPITIV3, 6HKWT4QG) / reg4 (ITXNQ843, 2F76GVEE, 4C479SU8, V3H4MP29),
  Claude references from `dev/annot_v2/`, reg4 not tuned on. `dev/show_io.py SLUG` prints each chunk input with its answer.
- **Reference inventory (verified):** 8 files: `dev/gold/murphy2005.yaml` (human); Claude-made: 4 in `dev/gold/`, 3 in `data/`
  (2F76GVEE, 4C479SU8, V3H4MP29), cleaned copies of all 7 in `dev/annot_v2/`.

## 2026-11-14 (night) — lenient claim-line parser  — KEPT (post-processing; exact on cached answers)
- **Finding:** 17 % of claim lines from the current prompt did not parse (1,090 of 6,304 in the answers of the running full
  run); on gold5 the repair call recovered 2 of 40 (paragraph-chunks) and 16 of 53 (sentence) — the rest were dropped silently.
  Causes: a value word the format has no code for (`T2/origin/hatchery-reared`, `peat chemistry/pH/high`, 645 + 334 lines),
  `;`-lists of causes, unit slashes (`kg/ha`), `F|...|N|exp` (a null written as an F line, 78).
- **Change (`pipeline/parse.py`):** the value word is kept verbatim on the property (`pH (high)`), no direction invented; a unit
  slash is `per`; an F line with language N is an N line; a `;` list of causes is ONE joint cause node ("A and B", plan rule:
  joint stays joint). Lines missing a cause or effect still fail. `PIPELINE_STRICT_PARSE=1` restores the old parser.
- **Result (paragraph-chunks, cached answers, 7 papers — V3H4MP29 not cached yet):** Murphy std F1 0.591 → 0.603, loose
  0.773 → 0.809; dev3 0.133 → 0.148; reg4 (3 papers) 0.083 → 0.092. Responses that need a repair call: 196 → 57 of 290.
- **Source check:** the recovered Murphy/6HKWT4QG/ITXNQ843/4CB9X9XE edges were read against their sentences; the wrong ones
  are wrong in the model's line (e.g. "low native forb cover causes glyphosate application"), not made wrong by the parser.
- **Not yet:** the sentence model and a second response set (replays of the b8_* runs follow).

## 2026-11-14 (night) — null convention check  — NO CHANGE
- Murphy gold: 15 negated edges; 7 put `unchanged` on the object ("not affected"), the others the negated direction. The CAMO
  v0.10.0 definitions of `negated` and `no_relationship` say the object keeps the qualifier a positive finding would use and
  is never `unchanged`. Our guard already follows that; the Murphy `unchanged` values predate the rule and are not copied.

## 2026-11-14 (night) — duplicate check keeps conditions  — KEPT (fidelity; no effect on the 8 papers)
- `guard.same_sentence_key` now includes dose, dose_level, comparator, temporal_extent: the same pair from one sentence at
  another dose or season is a different claim. Cached 8-paper scores identical.

## 2026-11-15 00:10 — lenient parser confirmed on 4 response sets per model; `|N;` per-effect nulls; property/property/change
- **Replay of b8_*_r1-2 and e8_*_r1-2 (4 distinct answer sets per model, 8 papers), strict vs lenient, mean [range]:**
  paragraph-chunks: Murphy std F1 0.571 [0.511–0.600] → 0.576 [0.551–0.594], null recall 0.583 → 0.683; dev3 0.125 → 0.142;
  reg4 0.130 → 0.145. Sentence: Murphy 0.550 [0.462–0.612] → 0.555 [0.539–0.592], null recall 0.450 → 0.633; dev3 0.084 →
  0.099; reg4 0.167 → 0.182. Better or equal on every group, both models. KEPT.
- Caveat: in runs started after the lenient code, the saved repair answer belongs to the lenient set of broken lines, so the
  strict replay of those runs is slightly disadvantaged; b8_sf_r1 (pre-change) shows the same direction.
- With the lenient parser live (b8_pc_r1): 3 of 479 lines unparseable (was about 14 %); repair recovered 1. Two more forms
  added afterwards: `effect|N;effect|N|exp` (every effect marked null -> N line; Murphy sentence model: these two lines carried
  the nulls the repair call used to rescue) and `thing/property/property/change`.

## 2026-11-15 00:10 — measured_attribute = head of an "X of Y" property  — KEPT (follows the CAMO definition)
- **Change (`expand.py`):** a property "size of year 1 rosettes" gives `measured_attribute: size`; the node name keeps the
  whole phrase. The schema defines measured_attribute as the quality (PATO: abundance, density, cover, height); the bearer
  belongs to the entity. `PIPELINE_HEAD_ATTRIBUTE=0` switches it off for comparisons.
- **Result (replay, one set each):** Murphy std F1: sentence baseline 0.517 → 0.544; paragraph-chunks baseline 0.597 → 0.583;
  enumeration prompt (paragraph-chunks) 0.439 → 0.594, strict 0.387 → 0.568. dev3 and reg4 identical in all three.

## 2026-11-15 00:10 — prompt `x_enum.txt` (list every outcome; null enumerations)  — INCONCLUSIVE, not adopted
- **Change:** three rule edits + two generic examples (non-Murphy wording): every listed outcome its own effect, null
  enumerations complete, ratio/joint treatment stays single, property "as specific as the paper".
- **Result, 2 runs per arm (baseline = identical copy of system.txt, same code), mean [range]:** paragraph-chunks Murphy
  0.579 [0.575–0.583] → 0.572 [0.551–0.594] (strict 0.524 → 0.547, recall 0.583 → 0.639), dev3 0.159 → 0.124, reg4 0.137 →
  0.153, null recall up on dev3/reg4. Sentence: Murphy 0.544 → 0.566, dev3 0.111 → 0.086, reg4 0.171 → 0.192.
- **Source check:** Murphy sentences 7 and 11 now give all nine / all four listed outcomes (the plan's f7 case is fixed in the
  raw answers). But on 6HKWT4QG (sentence model) the model dropped the T-codes ("root growth" instead of T1/root growth): the
  same drift as system_v1, probably from "as specific as the paper". Follow-up `x_enum2.txt`: property line restored, T-code
  rule and a separate-vs-joint cause rule added (runs f8_*).

## 2026-11-15 00:40 — `--keep-results` (paragraph selection keeps every Results prose paragraph)  — REVERTED (flag stays, off)
- **Change:** in `team_paper.keep_paragraph`, a Results paragraph that is not a caption or heading is kept whatever its cue
  score (the plan's "ecozone paragraph" case: 3KPITIV3, Murphy's leafing-phenology paragraph, 4CB9X9XE's "no seasonal
  variation"). Offline: +4.9 % input on the 8 papers, +2.9 % input tokens and 757 -> 773 calls over all 308.
- **Result, paragraph-chunks, 2 runs per arm, same code (b8_pc vs s8_pc):** Murphy std F1 0.579 [0.575–0.583] -> 0.537
  [0.533–0.541]; dev3 0.159 -> 0.095 (4CB9X9XE 0.173 -> 0.078 although only one sentence was added: the new paragraphs change
  the chunk packing, and the answers for the unchanged text change with it); reg4 0.137 -> 0.144. Worse; the sentence model is
  not affected (does not use this selection).

## 2026-11-15 01:00 — species fan-out merged  — KEPT (fidelity; found on a regression paper, judged on the source)
- **Finding:** the model spreads group words ("small trees", "seedling densities") over every species in the legend: 4C479SU8
  (paragraph-chunks) had 15 edges per sentence for T3–T17, species the sentences never name (the legend even lists "trees"
  as a variant of Populus tremuloides). Over the running full run's answers: 102 lines with >= 5 T-codes in one field
  (about 846 edges) in 55 of 903 answers.
- **Change (`expand.py`, `PIPELINE_FANOUT=0` = off):** when one line lists >= 4 bare T-codes with the same property and change,
  species that the cited sentences do not name (full name, "G. species", or a non-generic variant) are merged into ONE
  "multiple species" effect (composite); named species are kept. The same for a joint cause.
- **Result (replay of b8_*_r1-2):** Murphy, dev3, the whole sentence model: identical. Paragraph-chunks 4C479SU8: 297 -> 79
  edges, std precision 0.022 -> 0.076, F1 0.035 -> 0.076 (reg4 mean 0.137 -> 0.148). Not tuned: the rule was chosen from the
  source text before scoring.

## 2026-11-15 — full-corpus run of the submitted configuration (job `full_pc_1114`)  — safety-net graph
- **Config:** commit 250b105 code (pipeline/ was unmodified when the job started at 20:55), `--preprocess paragraph-chunks`,
  `system.txt`, cache on. Output: `dev/jobs/out/full_pc_1114/`.
- **Result:** 308 papers, 0 failed, 0 fell back to the sentence filter; 1 paper with no edges (TNY6N7LX); 27,429 edges,
  31,081 nodes, 2,684 null results; JSON Schema + linkml-validate passed; 4 h 41 min wall clock (shared endpoint, other
  jobs running in the second slot).
- **Tokens:** 3,114,029 in + 767,945 out = 3,881,974 (per paper 10,110 + 2,493). The 2026-11-13 sentence run: 2,264,689 +
  618,438 = 2,883,127 (7,353 + 2,008): +35 % tokens for +20 % edges and +28 % null results.
- **Gold papers (cached answers, so equal to one of the tp_new_pc runs):** Murphy std F1 0.584; out-of-sample on the
  cleaned annotations (dev/annot_v2): 4CB9X9XE 0.182, 3KPITIV3 0.111, 6HKWT4QG 0.108, ITXNQ843 0.254 (mean 0.164).
- **Parse losses:** 2,263 unparseable lines, 407 repaired, 1,883 dropped (about 8 % of lines; sentence run 1,417).

## 2026-11-15 01:40 — full run of the submitted configuration (`full_pc_1114`, paragraph-chunks, system.txt, code of 250b105)
- **Run:** 20:55–01:36 (16,873 s), 308 papers, 0 failed, 308 source_documents (285 DOIs from index.csv, 23 none);
  27,429 edges, 31,081 nodes, 2,684 null results; JSON Schema + linkml-validate passed.
- **Losses (old parser):** 20,220 claim lines parsed; 2,263 unparseable, repair recovered 407, 1,883 dropped (about 9 %).
- **Tokens:** 3,114,029 prompt + 767,945 completion; per paper 10,110 + 2,493, 757 calls. The 2026-11-13 sentence run:
  7,353 + 2,008 per paper, 321 calls. Paragraph-chunks costs +38 % prompt / +24 % completion tokens per paper over all 308
  papers (each chunk repeats system prompt + header; repair calls on 68 % of answers with the old parser).
- **Gold papers from this graph:** Murphy std F1 0.584, strict 0.526, loose 0.759, null recall 0.733. Original annotations:
  4CB9X9XE 0.182, 3KPITIV3 0.037, 6HKWT4QG 0.082, ITXNQ843 0.000. Cleaned (annot_v2): dev3 mean 0.133, reg4 mean 0.099.

## 2026-11-15 02:20 — lines that start with their language letter (`A|5|...`, `U|7|...`)  — KEPT (post-processing)
- **Finding:** 943 of about 28,400 claim lines in the full run's answers (3.4 %) start with A, U or D instead of F; the parser
  only looked at F|/N| lines, so they were ignored without being counted as lost. 2F76GVEE (sentence model): 64 answer lines,
  36 edges.
- **Change (`parse.py`, lenient only):** `A|`, `U|`, `D|` followed by a sentence number = an F line with that language (used
  when the line has no language field of its own).
- **Result (replay, all 2-run arms, same answers):** Murphy unchanged everywhere; baseline reg4 paragraph-chunks 0.148 -> 0.169,
  sentence 0.171 -> 0.211; dev3 paragraph-chunks 0.159 -> 0.167, sentence unchanged.

## 2026-11-15 02:20 — prompt `x_enum2.txt`  — REVERTED (system.txt stays)
- x_enum without "as specific as the paper", plus a T-code rule and a separate-vs-joint cause rule. 2 runs per model,
  replayed with the current code. Paragraph-chunks: Murphy 0.580 [0.570–0.590] vs baseline 0.579, dev3 0.139 vs 0.167, reg4
  0.167 vs 0.169. Sentence: Murphy 0.453 [0.371–0.536] vs 0.544, dev3 0.126 vs 0.111, reg4 0.187 vs 0.211. Worse on the
  sentence model, no gain on paragraph-chunks. With the current code x_enum (first version) is also no better: paragraph-
  chunks Murphy 0.572 / dev3 0.124 / reg4 0.169; sentence 0.566 / 0.086 / 0.238.

## 2026-11-15 02:20 — `--taxon-groups` (2 runs per model, current code)  — NOT ADOPTED (inconsistent; flag stays off)
- Paragraph-chunks: Murphy 0.576 vs 0.579; dev3 0.216 [0.215–0.217] vs 0.167 [0.163–0.171] (4CB9X9XE 0.17 -> 0.31: "rodents"
  gets the Rodentia ID); reg4 0.152 vs 0.169. Sentence: Murphy 0.566 vs 0.544; dev3 0.174 vs 0.111; reg4 0.167 vs 0.211.
- Why reg4 falls: one added legend line ("T18=small mammals") flips 4C479SU8 into the species fan-out (both models, both
  runs); 4C479SU8 0.25 -> 0.02 on the sentence model. Gains on the development papers, losses on the fixed regression set
  -> by the predeclared rule the simpler parent stays. Worth retrying only together with a fix for the fan-out.

## 2026-11-15 02:50 — prompt `x_grp.txt` (one rule: a group stays one thing; no T-codes for unnamed species)  — REVERTED
- 2 runs per model, current code. Paragraph-chunks: Murphy 0.536 [0.532–0.539] vs baseline 0.579 [0.575–0.583] (outside the
  range), dev3 0.132 vs 0.167, reg4 0.192 vs 0.169 (4C479SU8 0.08 -> 0.20: the fan-out is gone). Sentence: Murphy 0.538 vs
  0.544, dev3 0.093 vs 0.111, reg4 0.229 vs 0.211. Murphy (human gold) and dev3 fall on both models -> not adopted; the
  deterministic fan-out merge in expand.py stays the fix for the fan-out.

## 2026-11-15 03:15 — `--clean-variants` (legend without generic "common names")  — REVERTED (flag stays, off)
- Finding: the legend's "common name before (Genus species)" rule takes generic words: "Peromyscus maniculatus (species)",
  "Solidago canadensis (native oldfield species)", "Rudbeckia hirta (... trial)", "Populus tremuloides (trees)".
- A first, broad filter (v8, 1 run per model) also removed real names (reed canary grass); the narrow one (w8: a single
  generic word, or a phrase ending in species/trial/plants/...) was run 2x per model. Paragraph-chunks: Murphy 0.558
  [0.542–0.573] vs 0.579 [0.575–0.583], dev3 0.123 vs 0.167 (4CB9X9XE 0.17 -> 0.09), reg4 0.182 vs 0.169. Sentence: Murphy
  0.527 vs 0.544, dev3 0.135 [0.102–0.168] vs 0.111 (4CB9X9XE 0.02–0.25 between the two runs), reg4 0.221 vs 0.211.
  Murphy down on both models, dev3 in opposite directions -> simpler parent kept.
- General reading of tonight's input-side arms (5 of them): small input changes move single papers a lot (4CB9X9XE,
  4C479SU8) in both directions; none gave a consistent gain on both models. The consistent gains were all post-processing.

## 2026-11-15 03:25 — `--chunk-tokens 4000` (fewer, larger paragraph chunks; energy)  — REVERTED (flag stays, default 2,500)
- 2 runs, paragraph-chunks, 8 papers. Tokens per paper 7,846 + 2,041 (baseline mean) -> 6,624 + 1,960 (-14 %).
  Murphy std F1 0.548 [0.536–0.559] vs 0.579 [0.575–0.583], null recall 0.467 vs 0.700; dev3 0.112 vs 0.167; reg4 0.151 vs
  0.169. Worse on every group; accuracy is scored before energy.

## 2026-11-15 03:50 — CORRECTION to the `--clean-variants` and `--taxon-groups` entries: Murphy is unaffected by both
- Neither flag changes Murphy's input (its legend has no generic variant and no group word), and x_cv.txt / x_tg.txt are
  byte-identical to system.txt. So the Murphy numbers of w8_* and t8_* are additional draws of the BASELINE, not effects.
  Murphy paragraph-chunks over 6 identical-input draws: 0.575, 0.583 (b8), 0.542, 0.573 (w8), 0.575, 0.577 (t8): mean 0.571,
  range 0.542–0.583. Sentence over 6 draws: 0.544, 0.544, 0.511, 0.544, 0.544, 0.588.
- The decisions stand on dev3/reg4: clean-variants moves 4CB9X9XE in opposite directions on the two models (paragraph-chunks
  0.17 -> 0.09, sentence 0.07 -> 0.13); taxon groups lowers reg4 on both. Both flags stay off.

## 2026-11-15 03:50 — full run with tonight's code (`full_new_1115`, cache on: the answers of full_pc_1114, plus the latest
## refresh for the 8 reference papers; only repair calls went to the endpoint)  — the configuration to submit
- 308 papers, 0 failed, 308 source_documents; 30,208 edges (full_pc_1114: 27,429), 34,733 nodes, 2,869 null results;
  JSON Schema + linkml-validate passed. Unparseable lines 2,263 -> 223 (repair recovered 106; 128 dropped, listed in
  losses.jsonl with 147 records in all). 178 same-sentence repeats dropped. 1,152 s.
- Tokens as a fresh run would count them: 9,308 + 2,263 per paper (full_pc_1114: 10,110 + 2,493): fewer repair calls.
- Gold papers in this graph (one draw each): Murphy std F1 0.542 (the w8_pc draw, see above), dev3 0.152, reg4 0.167.
  Old full graph (different draw): Murphy 0.584, dev3 0.133, reg4 0.099.
- Model choice re-checked with tonight's code (2 runs each, replayed): paragraph-chunks vs sentence: Murphy 0.579 vs 0.544,
  dev3 0.167 vs 0.111, reg4 0.169 vs 0.211; pooled over the 7 Claude papers both 0.168. Paragraph-chunks stays (Murphy, the
  human gold, favours it in every draw); the sentence filter is about 27 % cheaper in tokens over the corpus.

## 2026-11-15 05:45 — thinking=on (max_tokens 12000), paragraph-chunks, 8 papers, 2 runs  — REJECTED (no output)
- Every call used the full 12,000 completion tokens (about 23 tok/s, 8–9 min per call) and returned no claim lines; several
  calls hit the 1,200 s total timeout. Both runs FAILED with "no edges at all" after 90–100 min. Thinking stays off: it
  is about 5x the completion tokens per call and, at this cap, produces nothing.

## 2026-11-15 05:50 — submitted configuration with tonight's code: 3 runs (b8_*_r1-3, replayed with the final code)
- Paragraph-chunks (submitted): Murphy std F1 0.579 [0.575–0.583], strict 0.518, loose 0.801, null recall 0.711; dev3
  0.169 [0.163–0.173]; reg4 0.170 [0.166–0.172]. Tokens per paper on the 8 papers about 7,800 + 2,050.
- Sentence filter: Murphy 0.554 [0.544–0.573]; dev3 0.111; reg4 0.212. Tokens per paper 5,693 + 1,493.
- The experiment prompts (`x_*.txt` + `.args`) are archived in `dev/experiments/prompts_overnight/` (copy one back to
  `pipeline/prompt/` to rerun an arm through the job runner).

## 2026-11-15 16:55 — node dedup in the merge (`pipeline/dedup.py`), post-processing only — KEPT (not committed yet)
- Problem: `merge()` concatenated papers, and node IDs are `node:{slug}_{hash of the parse key}`, so the same node was repeated in
  every paper, and inside one paper two parse keys could become the same node after later rewrites. out_test (3 papers, 265
  nodes): 4 groups repeated inside a paper, 1 shared by two papers (`Restoration`). The 21 repeated (s, p, o) triples all come
  from different sentences and are kept on purpose (same_sentence_key).
- Change: one node per distinct content (every field except id, spans, variable_key, embedding_*, annotator; the exact name IS
  part of the key, because the scorer reads the entity from the name when entity_term is a CURIE). The ID is
  `node:v_{sha1(content)[:12]}`, independent of paper order. Edges are untouched except their node references. Spans carry
  `sentence_id = {slug}:s{n}`. `variable_key` is written. Sidecars: node_map.csv, merged_nodes.csv, near_duplicates.csv.
- Check (exact, replayed with dev/replay.py from out_test/raw_responses.jsonl; the gold papers' answers are not cached
  locally, so gold5 was NOT rerun): 265 -> 260 nodes, 239 -> 239 edges, every edge byte-identical after resolving node
  references to content, linkml-validate OK, 2F76GVEE scores identical (std F1 0.160, strict 0.053, loose 0.171).
  Tests 303 passed. Both stage-1 models: model-independent (runs after the guard on any output).
