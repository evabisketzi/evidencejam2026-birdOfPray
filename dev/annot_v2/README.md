# Cleaned copies of the machine-made annotations

Only `dev/gold/murphy2005.yaml` is a human annotation. The other annotation files in `data/` were produced by Claude.
This folder holds cleaned copies of those seven files. The originals in `data/` and `dev/gold/` are unchanged.

| file | paper | in the gold5 evaluation set |
|---|---|---|
| `4CB9X9XE.yaml`, `3KPITIV3.yaml`, `6HKWT4QG.yaml`, `ITXNQ843.yaml` | the four out-of-sample papers | yes |
| `2F76GVEE.yaml`, `4C479SU8.yaml`, `V3H4MP29.yaml` | three further papers | no |

## What was changed

`dev/annot_fix.py` makes every change, and `CHANGES.md` lists each one per file. Steps 1 to 4 are wording and format
only. Step 5 is the result of reading every edge of the four gold5 files against its paper.

1. **Character offsets.** Three of the four gold5 files had no `start_char` / `end_char` on any span. Each span text is
   now located in the paper's markdown, so that `raw[start:end]` is the span. 1,190 spans were fixed over the seven
   files; 46 could not be located (mostly table captions) and are left as they were.
2. **Taxon IDs.** Species written as names became NCBITaxon IDs where our table has them (9 nodes, all in ITXNQ843).
3. **Terms name the entity only.** Method detail in brackets was removed from `entity_term` and `measured_attribute`
   ("black plastic mulch (1.8 m wide) over planting rows" → "black plastic mulch over planting rows"). The node `name`
   keeps the full wording.
4. **Hand edits** (`term_edits.tsv`, 38 rows): over-specified terms reduced to the entity, in the paper's own words
   ("broadcast glyphosate application without species targeting" → "glyphosate application"; "percent canopy cover" →
   "canopy cover"). This follows the Murphy annotation, where such detail sits in the dose, comparator and context
   fields. The three further papers got no hand edits.

5. **Claim-level corrections** (`edge_edits.yaml`), gold5 files only. All 209 edges were read against their quoted
   sentences and, where needed, the paper.
   - 4CB9X9XE (48 edges) and 6HKWT4QG (60 edges): nothing changed.
   - 3KPITIV3 (46 edges): 4 edges quoted a sentence that did not support them. Three light-ring edges quoted the one
     Results sentence that says "high average temperatures", while the edges (and the rest of the paper: Figure 5,
     its caption, the Discussion) say cold temperatures. The supporting sentence is quoted now. One table-derived edge
     quoted a sentence about a different provenance group.
   - ITXNQ843 (55 edges): 4 null results were stated in already-annotated sentences but only mentioned in the
     annotation notes ("did not reduce non-native grass and forb cover", "had no effect on non-native plant
     flowering"). They are edges now.
   - **Claims cited from other studies were removed** (11 edges: 1 in 3KPITIV3, 5 in 6HKWT4QG, 5 in ITXNQ843; 10
     nodes that only those edges used). The human Murphy annotation has none: all 25 of its findings are the study's
     own results, interpretations or recommendations, although the paper cites other work. Kept: the authors' own
     interpretations that cite a source in support ("A possible explanation ... is that ... (Molina et al., 2016)").
   - Edges after the review: 4CB9X9XE 48, 3KPITIV3 45, 6HKWT4QG 55, ITXNQ843 54.

All seven files pass `linkml-validate -s schema/causalmosaic.yaml -C CausalGraph`.

## What was checked and left alone

- Every `original_sentence` is in its paper. The ones that do not match character for character differ only by markup
  (`R <sup>2</sup>`, figure links), except for a few table-based claims.
- No predicate, causal language or node direction was changed: none was found wrong.
- Null-result objects without a direction, and edges that put the direction in the predicate (`disrupts`, `prevents`),
  were left as the annotator wrote them.

## Effect on our scores

Same pipeline output (the batch-0 control runs, 3 runs each), scored against the original and the cleaned files.
Mean over the four out-of-sample papers, with the lowest and highest run in brackets.

| model | annotations | standard F1 | strict F1 | loose F1 |
|---|---|---|---|---|
| sentence | original | 0.032 [0.031–0.034] | 0.014 [0.009–0.018] | 0.176 [0.170–0.180] |
| sentence | cleaned | 0.139 [0.125–0.150] | 0.106 [0.091–0.117] | 0.310 [0.307–0.314] |
| paragraph-chunks | original | 0.069 [0.066–0.075] | 0.058 [0.057–0.061] | 0.191 [0.185–0.202] |
| paragraph-chunks | cleaned | 0.156 [0.151–0.162] | 0.127 [0.122–0.134] | 0.301 [0.294–0.311] |

Almost all of the change comes from ITXNQ843 (loose F1 about 0.05 → 0.45–0.51) and 6HKWT4QG. On ITXNQ843 the pipeline
and the annotation state nearly the same claims; they failed to match only because every annotated subject carried
method detail. 4CB9X9XE did not change at all.

What still differs after cleaning is real, and it is the pipeline's side:

- **3KPITIV3:** the annotation attaches measurements to the species (*Picea glauca*, "blue ring frequency"); the
  pipeline writes a free-text variable ("blue rings").
- **4CB9X9XE:** the annotation uses the group's taxon ID for "rodents"; the pipeline writes "rodent density" as an
  environmental variable. The `--taxon-groups` flag targets this and has not been measured yet.

## How to use

```
EVAL_OTHERS_DIR=dev/annot_v2 .venv/bin/python dev/eval_murphy.py out/camo_graph.yaml --others
```

`dev/gold/` is write-protected by a hook. To make these the default, copy the four gold5 files there by hand
(`4CB9X9XE.yaml` replaces `4CB9X9XE.camo.yaml`).

## What the claim review did not cover

- Claims the papers make in sentences the annotation never quotes. The review checked each edge against its sentence;
  it was not a second, independent annotation of the whole paper.
- The three further papers (2F76GVEE, 4C479SU8, V3H4MP29; 285 edges) got the mechanical steps only.
- Open judgment call, left as it is: similar
  wording ("significantly lower with glyphosate" / "twice the abundance in exclosures") is labelled direct causal in
  ITXNQ843 and associational in 4CB9X9XE.

## Limits

These are still machine-made annotations. The clean-up makes them consistent with the Murphy conventions and
measurable; it does not make them human-checked. Numbers scored against them are not comparable with earlier
out-of-sample numbers in `dev/experiments/LOG.md`.
