# Entity failures (no_loose_match) on the 5 gold papers, sentence vs paragraph-chunks

**Inputs.** Scorer runs `score_sentence/` and `score_paragraph-chunks/` (raw mode, threshold 0.5) on the CACHED graphs
`graph_sentence.yaml` and `graph_paragraph-chunks.yaml` (current code, `prompt/system.txt`). Gold: `dev/gold/murphy2005.yaml`
(= YKQQZV93), `4CB9X9XE.camo.yaml`, `3KPITIV3.yaml`, `6HKWT4QG.yaml`, `ITXNQ843.yaml`.
**There is ONE cached sample per model, not repeated endpoint runs.** Endpoint noise (about ±0.04 standard F1 on Murphy) is not
reflected; treat per-paper cells under ~10 as anecdotal. Each paper has 46-72 gold edges.

**Scope.** Only `no_loose_match`: 166 FN + 217 FP (sentence), 170 FN + 219 FP (paragraph-chunks) = 772 items, the same counts as
`score.json`. I re-ran `dev/score/match.py` on the same files to get node details.

**Method.** Each FN is compared with our edge from the same sentence that is closest by the scorer's `near_sim`. If no edge of
ours cites that sentence, it is compared with our closest edge anywhere in the paper. Each FP is compared the same way with the
gold edges. Classes a-d apply only when the two edges state the same claim. Each item was then labelled by hand (one annotator,
one pass), and identical (gold, ours) pairs got the same label. The d/e boundary is a judgement call.

**Class rule (the first that applies wins):** (a) group vs species: one side names a group, the other a species (either way).
(b) treatment vs trait/state as cause: an action by the authors on one side, a presence/density/trait/state on the other.
(c) organism missing on a measurement, on one side only. (d) same concept in other words, below the Jaccard threshold of 0.5.
(e) not in the other graph: for an FP, a claim the gold does not annotate; for an FN, no edge of ours states that claim.
(f) other: `taken` = the scorer finds an entity-agreeing counterpart, but the one-to-one assignment gave it to another edge;
`combined` = one edge for a listed set or an umbrella term ("April and May", "latewood anomalies"); `moderator` = a moderator
encoded as a cause of the treatment or its effectiveness; `swap` = subject and object reversed; `wrongorg`/`role` = the organism
is attached to the wrong node, or the consumer is swapped with the consumed plant.

## 1. Counts per class x FN/FP x model
| class | FN sentence | FN para-chunks | FP sentence | FP para-chunks | total | share |
|---|---:|---:|---:|---:|---:|---:|
| (a) group vs species | 19 | 11 | 26 | 15 | 71 | 9.2% |
| (b) treatment vs trait as cause | 12 | 7 | 11 | 11 | 41 | 5.3% |
| (c) organism missing on a measurement | 2 | 6 | 2 | 5 | 15 | 1.9% |
| (d) paraphrase below threshold | 53 | 59 | 71 | 93 | 276 | 35.8% |
| (e) claim not in the other graph | 55 | 56 | 80 | 80 | 271 | 35.1% |
| (f) other | 25 | 31 | 27 | 15 | 98 | 12.7% |
| total | 166 | 170 | 217 | 219 | 772 | 100% |

Breakdown of (f): taken 64 (29 sentence / 35 para), combined 19 (18/1), moderator 6, swap 4, wrongorg 3, role 2.
Breakdown of (e): 160 FP, of which 112 come from sentences the gold does not annotate at all. 111 FN, of which 78 are gold
sentences that none of our edges cite. Whether those sentences reached the model (preprocessing) was NOT checked.

## 2. Counts per paper x class, per model (total = FN+FP)
| paper | model | a | b | c | d | e | f | total (FN+FP) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| murphy2005 | sentence | 1 | 0 | 0 | 1 | 6 | 4 | 12 (5+7) |
| murphy2005 | paragraph-chunks | 0 | 0 | 0 | 0 | 14 | 5 | 19 (4+15) |
| 4CB9X9XE | sentence | 38 | 1 | 2 | 0 | 40 | 5 | 86 (42+44) |
| 4CB9X9XE | paragraph-chunks | 14 | 3 | 7 | 18 | 21 | 9 | 72 (36+36) |
| 3KPITIV3 | sentence | 0 | 17 | 0 | 22 | 48 | 19 | 106 (43+63) |
| 3KPITIV3 | paragraph-chunks | 0 | 8 | 0 | 35 | 53 | 2 | 98 (42+56) |
| 6HKWT4QG | sentence | 0 | 5 | 2 | 9 | 12 | 22 | 50 (26+24) |
| 6HKWT4QG | paragraph-chunks | 4 | 6 | 2 | 8 | 16 | 24 | 60 (37+23) |
| ITXNQ843 | sentence | 6 | 0 | 0 | 92 | 29 | 2 | 129 (50+79) |
| ITXNQ843 | paragraph-chunks | 8 | 1 | 2 | 91 | 32 | 6 | 140 (51+89) |

## 3. Examples (G = gold, P = ours; S = sentence)
### (a) group vs species. In 67 of the 71, ours is the more specific side; 36 use Peromyscus/Zapus where the gold has "rodents".
- 4CB9X9XE, sentence, FN. G: rodent population density -> removal of Andropogon gerardii seed | P: density of Peromyscus maniculatus -> consumption of Andropogon gerardii | S: "Andropogon gerardii, which was ignored most months, was consumed during June and July when rodent densities were highest"
- 4CB9X9XE, paragraph-chunks, FP. G: rodent granivory on planted prairie species -> decreased recruitment of planted prairie species | P: population density of Peromyscus maniculatus -> decreased recruitment of native prairie plants | S: "...normal to high population levels of rodents being maintained, which in turn exerts intense granivore pressure thereby inhibiting recruitment by some native prairie plants."
- ITXNQ843, sentence, FP. G: glyphosate -> increased cover of Lepidium densiflorum (plus a group edge "increased non-native forb cover") | P: glyphosate -> increased cover of Medicago lupulina (also Verbascum, Cirsium, Chrysanthemum) | S: "Increased cover was mainly due to Lepidium densiflorum ... and Medicago lupulina ... and some species unique to sites, such as Chrysanthemum leucanthemum ... Verbascum thapsus ..."
### (b) treatment vs trait as cause
- 3KPITIV3, sentence, FN. G: Transfer of Cold Boreal Picea glauca seed sources to the test site -> spring frost ring frequency | P: Occurrence of provenances from Cold Boreal ecozone -> vulnerability to spring frosts | S: "Provenances from the most northern ecozone (Cold Boreal) were the most vulnerable to spring frosts, but had very low instances of light, double, and blue rings."
- 6HKWT4QG, sentence, FN. G: Site preparation plus continued competition control -> root egress of aspen | P: Absence of competing vegetation -> percent root egress of Populus tremuloides | S: "Comparing the three sites at CDC, the percent root egress was highest in the Mulch (least competition)."
- ITXNQ843, paragraph-chunks, FP (reverse case). G: Decreased non-native grass cover -> increased non-native forb cover | P: glyphosate application -> increased cover of non-native forbs | S: "Increased non-native forbs with glyphosate was likely due to a larger reduction in non-native grasses, resulting in release from competition..."
### (c) organism missing on a measurement
- 4CB9X9XE, paragraph-chunks, FN. G: seed production of planted prairie species -> rodent consumption of planted prairie plants | P: Peak seed production -> consumption of planted prairie species (no rodent) | S: "The exceptions were August-September, when planted prairie species accounted for 87% of plants consumed and coincided with their peak seed production."
- 6HKWT4QG, sentence, FP. G: grass cover of competing vegetation -> root mass of competing vegetation | P: grass cover -> root mass | S: "...the principal component analysis also showed a positive correlation between root mass with grass cover and between forb mass and the height of the competing vegetation."
- ITXNQ843, paragraph-chunks, FN. G: repeated herbicide application every 2-3 years -prevents-> reinvasion by non-native plants | P: repeated herbicide application -prevents-> Reinvasion | S: "...repeated herbicide application has been recommended for every 2-3 yr to prevent reinvasion (Holl et al. 2014)."
### (d) paraphrase below threshold. 141 of the 276 come from one gold-side cause, explained under Conclusions.
- ITXNQ843, sentence, FN. G: Broadcast glyphosate application (not species-targeted) [entity_term "broadcast glyphosate application without species targeting"] -> decreased cover of Bromus inermis | P: glyphosate application -> decreased cover of Bromus inermis (object identical) | S: "P. compressa at all sites, and B. inermis and P. pratensis at Site 2, were significantly reduced with glyphosate relative to the control..."
- 3KPITIV3, paragraph-chunks, FN. G: latitude of the seed-source origin -> light ring intensity | P: latitude of seed sources -> intensity of light rings | S: "The latitude of the seed sources was negatively correlated with the intensity of light, blue, and double rings (Table 2)."
- 4CB9X9XE, paragraph-chunks, FN. G: Installation of small-mammal exclosures -> abundance of planted native seedlings | P: Rodent exclosure -> abundance of planted native seedlings | S: "The exclosed plots had twice the abundance of planted native seedlings (F = 5.92, P = 0.0196) and significantly higher richness of planted species..."
### (e) not in the other graph
- 3KPITIV3, sentence, FP. P: Presence of xylem anomalies -enables-> Early indicator of maladaptation to climate | nearest G: interrupted xylem development -> double ring frequency | S: "We conclude that xylem anomalies may serve as a sensitive early indicator of maladaptation to climate before populations experience tree dieback or mortality."
- 3KPITIV3, paragraph-chunks, FN. G: mean annual temperature at the seed-source origin -> light ring intensity | no edge of ours cites the sentence; the closest is "High temperature -> vulnerability to late spring frost" | S: "Mean annual temperature and the end of the frost free period were positively correlated with these latewood anomalies..."
- ITXNQ843, paragraph-chunks, FP. P: establishment and spread of perennial invasive forbs -disrupts-> grassland restoration | S: "...in the longer term, establishment and spread of perennial invasive forbs may be detrimental to grassland restoration." (the gold has no edge from this sentence)
### (f) other
- 6HKWT4QG, paragraph-chunks, FN, taken. G: Planting aspen nursery stock of a given size class -> two-year height growth increment | P: root-to-shoot ratio of Populus tremuloides -> height growth of Populus tremuloides. The entities "agree" only because the gold intervention node carries the Populus taxon in `applied_to`; semantically this is (b). | S: "...short size class seedlings had greater two-year height growth over the tall size class on four of the six sites."
- 3KPITIV3, sentence, FN, combined. G: April minimum temperature -> spring frost ring frequency (plus a separate May edge) | P: Mild temperatures in April and May -> spring frost rings | S: "By contrast, spring frost rings were associated with mild temperatures in April (R2 = 0.38, p < 0.001) and May (Figure 4)."
- ITXNQ843, sentence, FP, moderator. G: Dominance of perennial non-native grasses -moderates-> decreased non-native grass cover | P: Presence of perennial non-native grass -disrupts-> Steam control | S: "Additionally, perennial nonnative grasses dominating our sites are difficult to kill with steam (Wei et al. 2010)."

## 4. Conclusions
- **(d) and (e) are 71% of entity failures (276 + 271 of 772), but much of (d) is not ours to fix.** 141 of the 276 (d) items are
  ITXNQ843 edges whose object is right and whose subject is "glyphosate application", "steam application" or "cutting". The gold
  `entity_term` there is a long description ("broadcast glyphosate application without species targeting", "commercial hot-water
  steam application (325 °C...)"), and the scorer prefers it to the node name. Compared with the gold node name (parenthetical
  removed), all 141 pass Jaccard >= 0.5. This comes from the gold's annotation style plus the scorer; do NOT chase it in the
  prompt. The remaining ~135 (d) items are real paraphrase, mostly 3KPITIV3 climate variables ("Low temperatures in March" vs
  "March minimum temperature at the test site") and "Rodent exclosure" vs "small-mammal exclosures". A prompt rule to keep the
  paper's own variable name with its qualifiers (month, minimum/mean, where measured) is a legitimate, modest fix.
- **(e) is mostly a difference in what gets annotated, plus a recall gap.** 112 FP come from sentences the gold never annotates
  (conclusions, implications, mechanisms such as "anomalies may serve as an early indicator"). They are a precision cost of
  extracting assertional or speculative claims, which is a prompt and scope decision, not entity naming. 78 FN are gold sentences
  that no edge of ours cites. Check those against the preprocessing sidecar before deciding between preprocessing and prompt;
  this was not done here.
- **(a) is the clearest prompt-fixable class (71, 9.2%) and is concentrated in 4CB9X9XE with the sentence model (38 of 86 items
  there).** In 67 of the 71, ours is more specific than the gold: Peromyscus maniculatus for "rodents", Elymus/Lespedeza for
  "planted prairie species". The sentence model also emits parallel Elymus and Lespedeza copies of one group claim; check whether
  the species legend or expand stage produces them. Fix: name the level the sentence asserts (a group if it speaks of rodents or
  planted species) and name a species only when the claim is species-specific. Paragraph-chunks has fewer (a) here (14 vs 38),
  so the effect will differ by model.
- **Do not chase (b) or most of (f).** (b) has 41 items; the gold usually turns the text's state into an intervention ("Transfer of
  Cold Boreal seed sources" where the text says "provenances from Cold Boreal"; "Site preparation plus competition control" where
  it says "least competition"). Our wording follows the paper. Of (f), 64 are `taken`: the entities agree only through a shared
  taxon (39 in 6HKWT4QG, 21 with the gold subject "Planting aspen nursery stock...") and the counterpart went to another edge, a
  scorer artefact. The real prompt items in (f) are the 19 `combined` cases (18 from the sentence model, all 3KPITIV3): emit one
  edge per listed month or variable ("April and May"; "these latewood anomalies" = light, blue, double rings).
- (c) is small (15, 1.9%) and not a priority. All counts come from one cached sample per model; re-check any prompt change with
  repeated endpoint runs for both models.
