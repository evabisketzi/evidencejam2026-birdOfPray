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
