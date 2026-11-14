# Overnight evaluation report

Run folder: `/home/kbuzko/Code/EvidenceJam/evidencejam2026-lane1/dev/overnight/20261113_202118`  ·  generated 2026-11-14 04:06:29

## 1. Phase A: baseline vs Socratic on the dev set


Gold: Murphy 2005 (gold doc `murphy2005`, corpus slug YKQQZV93) and 4CB9X9XE. Raw mode (duplicate edges not collapsed), default object-attribute threshold. Tokens and seconds are per paper from `tokens.csv`; the dev runs bypass the cache, so the timings are real.

| variant | paper | standard P / R / F1 | strict F1 | loose F1 | null P / R | causal_language acc | finding recall | prompt tok/paper | completion tok/paper | seconds/paper |
|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|
| baseline | 4CB9X9XE | 0.019 / 0.021 / 0.020 | 0.020 | 0.039 | 0.000 / 0.000 | 1.000 | — | 5709 | 1144 | 324 |
| baseline | murphy2005 | 0.506 / 0.542 / 0.523 | 0.456 | 0.846 | 0.615 / 0.533 | 0.692 | 0.720 | 6271 | 1925 | 433 |
| **baseline** | **micro** | 0.305 / 0.333 / 0.319 | 0.279 | 0.518 | 0.500 / 0.333 | 0.700 | 0.720 | 5990 | 1534 | 379 |
| socratic | 4CB9X9XE | 0.146 / 0.146 / 0.146 | 0.146 | 0.188 | 0.333 / 0.111 | 0.714 | — | 5761 | 1267 | 353 |
| socratic | murphy2005 | 0.485 / 0.458 / 0.471 | 0.443 | 0.914 | 0.467 / 0.467 | 0.667 | 0.600 | 6349 | 2071 | 525 |
| **socratic** | **micro** | 0.345 / 0.333 / 0.339 | 0.322 | 0.619 | 0.444 / 0.333 | 0.675 | 0.600 | 6055 | 1669 | 439 |

### Error reasons

False negatives are gold edges we missed; false positives are our edges with no gold match.

| variant | list | no loose match | attribute differs | opposite direction | null mismatch | other |
|---|---|---:|---:|---:|---:|---:|
| baseline | false negatives | 48 | 24 | 1 | 7 | 0 |
| baseline | false positives | 64 | 24 | 1 | 2 | 0 |
| socratic | false negatives | 42 | 31 | 2 | 5 | 0 |
| socratic | false positives | 43 | 31 | 2 | 0 | 0 |

### Found by baseline, missed by Socratic: 10 gold edge(s)

1. [murphy2005 f2] `[Present] Sanguinaria canadensis initial planting density --causes--> [Decreased] Alliaria petiolata rosette count`  
   why missed: right entities, object attribute differs (similarity 0.25)
2. [murphy2005 f2] `[Present] Sanguinaria canadensis initial planting density --causes--> [Decreased] Alliaria petiolata silique count`  
   why missed: right entities, object attribute differs (similarity 0.25)
3. [murphy2005 f13] `[Present] initial planting density of Sanguinaria canadensis ramets --associated_with--> [Increased] number of leaves of Sanguinaria canadensis (increased)`  
   why missed: right entities, object attribute differs (similarity 0.00)
4. [murphy2005 f13] `[Present] initial planting density of Sanguinaria canadensis ramets --associated_with--> [Unchanged] number of leaves of Sanguinaria canadensis (unchanged relative to highest density)`  
   why missed: right entities, object attribute differs (similarity 0.00)
5. [murphy2005 f17] `[Increased] Sanguinaria canadensis planting density (density treatments) --causes--> [Unchanged] change in number of Alliaria petiolata seedlings between late spring and autumn (NULL)`  
   why missed: right entities, object attribute differs (similarity 0.20)
6. [murphy2005 f18] `[Present] Sanguinaria canadensis initial ramet density --associated_with--> [Increased] Alliaria petiolata rosette number (increased)`  
   why missed: right entities, object attribute differs (similarity 0.00)
7. [murphy2005 f18] `[Present] Sanguinaria canadensis initial ramet density --associated_with--> [Increased] Alliaria petiolata rosette size (increased)`  
   why missed: right entities, but one side is a null result and the other a positive claim (null flags disagree)
8. [murphy2005 f19] `[Increased] Sanguinaria canadensis density, increased --causes--> [Decreased] Alliaria petiolata rosette abundance after year 1 autumn, decreased (NULL)`  
   why missed: right entities, object attribute differs (similarity 0.12)
9. [murphy2005 f23] `[Introduced] planting of Sanguinaria canadensis --prevents--> [Decreased] invasion by Alliaria petiolata`  
   why missed: right entities, object attribute differs (similarity 0.00)
10. [murphy2005 f33] `[Introduced] planting of species like Sanguinaria canadensis --contributes_to--> [Decreased] spread of Alliaria petiolata`  
   why missed: right entities, opposite direction

### Found by Socratic, missed by baseline: 10 gold edge(s)

1. [4CB9X9XE] `[Increased] rodent granivory on planted prairie species --causes--> [Decreased] recruitment of planted prairie species`  
   why missed: no loose match (the pair of entities was not found)
2. [4CB9X9XE] `[Introduced] Installation of small-mammal exclosures --associated_with--> [Increased] species richness of planted prairie species`  
   why missed: no loose match (the pair of entities was not found)
3. [4CB9X9XE] `[Introduced] Installation of small-mammal exclosures --associated_with--> [Increased] number of Elymus canadensis seedlings`  
   why missed: no loose match (the pair of entities was not found)
4. [4CB9X9XE] `[Introduced] Installation of small-mammal exclosures --associated_with--> [Increased] recruitment of oldfield plants (NULL)`  
   why missed: no loose match (the pair of entities was not found)
5. [4CB9X9XE] `[Increased] rodent granivory on planted prairie species --contributes_to--> [Decreased] restoration success of planted tallgrass prairie`  
   why missed: no loose match (the pair of entities was not found)
6. [4CB9X9XE] `[Increased] Mustela erminea abundance --contributes_to--> [Decreased] rodent population density`  
   why missed: no loose match (the pair of entities was not found)
7. [murphy2005 f21] `[Increased] Sanguinaria canadensis density (increased) --causes--> [Decreased] Alliaria petiolata vegetative allocation (affected)`  
   why missed: right entities, but one side is a null result and the other a positive claim (null flags disagree)
8. [murphy2005 f21] `[Increased] Sanguinaria canadensis density (increased) --causes--> [Decreased] Alliaria petiolata reproductive allocation (affected)`  
   why missed: right entities, but one side is a null result and the other a positive claim (null flags disagree)
9. [murphy2005 f24] `[Occurred] transplanting of Sanguinaria canadensis --causes--> [Increased] Alliaria petiolata spring population size (remained high) increased (NULL)`  
   why missed: right entities, object attribute differs (similarity 0.33)
10. [murphy2005 f26] `[Increased] Sanguinaria canadensis ramet density --causes--> [Increased] Sanguinaria canadensis competitive success against Alliaria petiolata`  
   why missed: right entities, object attribute differs (similarity 0.33)

### Winner

**baseline** (system.txt): Socratic did not meet either condition. micro standard F1 baseline 0.319 vs Socratic 0.339 (difference +0.020); null recall 0.333 vs 0.333 (difference +0.000)

Rule: Socratic wins only if its micro standard F1 is at least 0.05 above baseline, or within 0.02 of baseline with null recall at least 0.15 higher; otherwise baseline wins.

## 2. Full runs

### full_baseline (system.txt)

- papers: **308 ok**, **0 failed** (of 308); retries: 0 logged (0 gave up)
- tokens: total prompt 2,264,689, completion 618,438; per paper median prompt 6880, completion 1824
- wall clock: 3:49:34
- graph: 22,938 edges, 23,840 nodes, 2,100 null results; edges per paper median 66.0, min 7, max 356
- validation: YAML OK, JSON OK (JSON Schema + linkml-validate)
- papers with 0 edges (0): none

### full_socratic (system_socratic.txt)

- papers: **308 ok**, **0 failed** (of 308); retries: 0 logged (0 gave up)
- tokens: total prompt 2,291,290, completion 624,228; per paper median prompt 6980, completion 1813
- wall clock: 3:38:39
- graph: 21,611 edges, 23,399 nodes, 2,162 null results; edges per paper median 65.0, min 4, max 294
- validation: YAML OK, JSON OK (JSON Schema + linkml-validate)
- papers with 0 edges (0): none

## 3. Baseline vs Socratic, side by side

| | baseline | socratic |
|---|---:|---:|
| papers ok | 308 | 308 |
| papers failed | 0 | 0 |
| edges | 22,938 | 21,611 |
| nodes | 23,840 | 23,399 |
| null results | 2,100 | 2,162 |
| edges per paper (median) | 66.0 | 65.0 |
| papers with 0 edges | 0 | 0 |
| prompt tokens (total) | 2,264,689 | 2,291,290 |
| completion tokens (total) | 618,438 | 624,228 |
| completion tokens / paper (median) | 1824.0 | 1813.0 |
| wall clock | 3:49:34 | 3:38:39 |
| retries | 0 | 0 |

Ten papers where the variants differ most in edge count:

| paper | baseline edges | socratic edges | difference |
|---|---:|---:|---:|
| 4C479SU8 | 199 | 16 | -183 |
| DX4T38CC | 356 | 232 | -124 |
| IBH9XBA8 | 243 | 135 | -108 |
| DC4NC848 | 158 | 57 | -101 |
| CEDDB25C | 131 | 37 | -94 |
| QGPQKL8S | 79 | 157 | +78 |
| 2F76GVEE | 8 | 76 | +68 |
| P8ZTCQ4R | 47 | 109 | +62 |
| 2UCS49MR | 104 | 47 | -57 |
| 8N7KYM3U | 108 | 52 | -56 |

## 4. Timing and what went wrong

| phase | start | end | duration | status | note |
|---|---|---|---:|---|---|
| tests | 20:21:19 | 20:22:01 | 0:00:42 | ok |  |
| dev_baseline | 20:22:01 | 20:29:23 | 0:07:22 | ok |  |
| dev_socratic | 20:29:23 | 20:38:16 | 0:08:53 | ok |  |
| dev_comparison | 20:38:16 | 20:38:16 | 0:00:00 | ok |  |
| full_baseline | 20:38:16 | 00:27:50 | 3:49:34 | ok |  |
| full_socratic | 00:27:50 | 04:06:29 | 3:38:39 | ok |  |

Problems: no phase failed.
Skipped: nothing.
