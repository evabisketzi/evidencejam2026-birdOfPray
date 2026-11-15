# Evidence Jam 2026 — Lane 1: Causal Annotation

Turns the 308 ecological restoration articles in `corpus/` into one merged causal graph in the Causal Mosaic Schema
(CAMO v0.10.0), as YAML and JSON, validated against the schema. A language model reads; plain code writes the graph.

**[Pipeline explorer (website)](https://evabisketzi.github.io/evidencejam2026-birdOfPray/)**: follow one claim from sentence to graph, read how each stage
works, and replay the pipeline on the reference papers in your browser.

**Docs:** [Method](reports/METHOD.md) · [Results](reports/RESULTS.md) · [Ontology grounding](ontology/GROUNDING.md) ·
[Experiment log](dev/experiments/LOG.md)

[![Pipeline: 308 articles in, one merged CAMO graph out. Six stages; only stage 3 calls the model.](docs/pipeline-readme.svg)](https://evabisketzi.github.io/evidencejam2026-birdOfPray/)

## Quick start

Needs Linux (x86-64 or aarch64), Python 3 with `venv` (tested on 3.12), internet on the first run, and access to the
BRINE endpoint.

```bash
git clone https://github.com/evabisketzi/evidencejam2026-birdOfPray.git
cd evidencejam2026-birdOfPray
export BRINE_URL=...  BRINE_MODEL=...  BRINE_API_KEY=...   # environment only; never commit the key
./run.sh corpus/ output/
```

The result is `output/camo_graph.yaml` and `output/camo_graph.json`. The first run builds `.venv/` from the pinned
`requirements.txt`. A full run takes about 4 h 40 min; a rerun on unchanged input takes minutes, because answers are
cached.

**No key?** Test the plumbing with the bundled fake endpoint (Python 3.12+; the graph it produces means nothing):

```bash
python3 dev/mock_endpoint.py 18999 &
BRINE_URL=http://127.0.0.1:18999/v1 BRINE_MODEL=mock BRINE_API_KEY=mock ./run.sh corpus/ out_mock/ --limit 5 --no-cache
kill %1
```

## How it works

| stage | what happens | model call |
|---|---|---|
| 1. Preprocess | Clean each article, keep the paragraphs that state findings, number the sentences, list species as codes (`T1`, `T2`); chunks of ≤ 2,500 tokens | no |
| 2. Ground taxa | Look up each species in a NCBITaxon table built from the NCBI taxonomy | no |
| 3. Extract | Qwen writes one short line per causal claim the authors make about their own study | **yes**, one per chunk |
| 4. Parse and expand | Turn each line into CAMO nodes and edges; ground the other terms in [8 ontologies](#ontologies) | no |
| 5. Guard and merge | Repair or drop anything the schema would reject, remove repeats, add a `source_documents` entry with its DOI for every `index.csv` row | no |
| 6. Write and validate | Write YAML and JSON; check with JSON Schema and `linkml-validate`. A failing paper never stops the run | no |

One claim as the model writes it (format defined in `pipeline/prompt/system.txt`):

```
F|12|T1/initial planting density/+/tax|c|T2/number of individuals/-|D|exp|stage=seedling|dose=9-11 ramets/m2
```

`F` finding (`N` null result) · `12` sentence number · cause and effect as entity/attribute/change(/type) ·
`c` causes · `D` direct (`U` hedged, `A` associational) · `exp` design · optional conditions.
The model never writes YAML, IDs or character offsets, so it cannot produce an invalid graph.
Details: [reports/METHOD.md](reports/METHOD.md).

### Ontologies

The model never writes an ID. Code looks terms up in committed indexes (`ontology/ontology_index/`, versions in
`manifest.json`) and writes an ID only when exactly one label or exact synonym matches; anything else stays free text,
because a wrong ID is worse than none.

| ontology | grounds |
|---|---|
| NCBITaxon | species and higher taxa (`entity_term` of taxon nodes) |
| ENVO | environments, environmental materials and processes |
| ChEBI | chemicals (nutrients, herbicides) |
| GO | biological processes |
| ELMO | ecological entities and processes from the Ecolink Model Ontology |
| PATO | measured attributes (height, mass, amount) |
| PO, UBERON | life stages of plants and animals |

`units.yaml` holds the unit table. How the indexes are built: [ontology/GROUNDING.md](ontology/GROUNDING.md).

## Results at a glance

Our own scorer, not the judges' score.

| | |
|---|---|
| Murphy 2005 (the only human reference) | standard F1 **0.579** (3 runs, 0.575–0.583), null-result recall 0.71 |
| Full corpus | 308 papers, 0 failed, 30,208 edges, 0 schema errors |
| Cost | about 9,300 prompt + 2,300 completion tokens per article, about 2.5 calls |

On the seven Claude-made references standard F1 is about 0.17, partly because they word entities differently.
Everything else, including ablations and failure cases: [reports/RESULTS.md](reports/RESULTS.md).

## Outputs

All in the output directory given to `run.sh`.

| file | contents |
|---|---|
| `camo_graph.yaml`, `camo_graph.json` | **the result**: one merged CAMO graph |
| `run_log.json`, `tokens.csv` | settings used; per-paper counts, errors, tokens and time |
| `losses.jsonl` | claim lines lost before the graph, and why |
| `raw_responses.jsonl` | every model answer; `dev/replay.py` rebuilds the graph from it without the endpoint |
| `doi_report.csv`, `ontology_report.json`, `retries.csv` | DOI per paper, ontology lookups, retried calls |

Re-validate by hand: `.venv/bin/linkml-validate -s schema/causalmosaic.yaml -C CausalGraph output/camo_graph.yaml`.
Cached answers live in `.cache/extract/`; delete it to start fresh.

## Options

`./run.sh CORPUS_DIR OUTPUT_DIR [options]`. The defaults are the submitted configuration.

| option | default | what it does |
|---|---|---|
| `--docs A,B` / `--limit N` | all | only these papers / the first N of `index.csv` |
| `--smoke YKQQZV93` | | one uncached call on one paper: tokens, speed, parse stats |
| `--concurrency N` | 4 | parallel model calls |
| `--preprocess` | `paragraph-chunks` | also `paragraph`, `sentence`, `sentence-chunks` |
| `--ontology` | `lookup` | exact matches only; `select` lets the model choose (one extra call per paper); `off` |
| `--prompt FILE`, `--max-tokens N`, `--thinking on/off` | `system.txt`, 3000, off | prompt from `pipeline/prompt/`, output limit, reasoning mode |
| `--refresh-cache` / `--no-cache` | | ask again and store / neither read nor write the cache |

Full list: `.venv/bin/python -m pipeline.main --help`.

## Repository

| path | what it is |
|---|---|
| `run.sh` | the one command |
| `pipeline/` | the pipeline; `main.py` is the entry point, `prompt/` holds the prompts |
| `data/` | lookup tables (NCBITaxon names, verified terms, JSON Schema, precomputed token counts) |
| `ontology/` | term grounding; `ontology_index/` holds the 8 committed indexes and `units.yaml` |
| `corpus/`, `schema/`, `example/` | given by the organisers; never modified |
| `tests/` | `pytest` unit and end-to-end tests |
| `dev/` | scorer, gold annotations, replay, mock endpoint, preflight, experiment log |
| `reports/` | `METHOD.md`, `RESULTS.md` |
| `docs/` | the website and the figures |

## Development

```bash
.venv/bin/python -m pip install -r requirements-dev.txt          # after one ./run.sh
.venv/bin/python -m pytest -q tests                              # about 1–1.5 min, no endpoint
.venv/bin/python dev/eval_murphy.py output/camo_graph.yaml --others   # score a graph
dev/preflight.sh                                                 # clean-checkout check before pushing
```

How we evaluate and run experiments: [reports/METHOD.md](reports/METHOD.md#evaluation). Never commit the key, and
never edit `corpus/`, `schema/`, `dev/gold/` or `data/camo.schema.json`.

## Troubleshooting

| symptom | fix |
|---|---|
| `missing environment variable(s): BRINE_...` | export all three `BRINE_*` variables in the same shell |
| `The virtual environment was not created successfully` | install `python3-venv`, or set `PYTHON=` to a Python that has `venv` |
| HTTP 404 from the endpoint | check `BRINE_URL`; it works with or without `/v1` |
| `no edges at all: extraction failed for every document` | endpoint down, wrong model or key: run `--smoke YKQQZV93` and read `retries.csv` |
| a paper is missing claims | look it up in `losses.jsonl` and `run_log.json` |

## Acknowledgements

Thanks to the Evidence Jam 2026 organisers for the corpus, the Causal Mosaic Schema, the hand-checked Murphy 2005
annotation and the shared model endpoint. Team: evabisketzi, lilac-haze, lorelyai. We used Claude Code (Anthropic)
during development.

---

## The challenge

A summary of the organisers' brief for Lane 1.

**Task.** Write a script that annotates the 308 ecological restoration articles in `corpus/` with the Causal Mosaic
Schema (CAMO v0.10.0, `schema/causalmosaic.yaml`), in YAML and JSON, using ontologies wherever possible. The articles
are markdown converted from PDF, so they carry conversion artefacts; `corpus/index.csv` gives each one's DOI and
bibliographic details. `example/` holds a hand-checked annotation of one article (Murphy 2005) and its PDF.

**What a CAMO graph holds.** A node is a state or change of an attribute of an entity (entity, measured attribute,
qualifier), not a thing. An edge is a causal claim between two nodes: a predicate, the authors' causal language, the
original sentence and optional causal features. Polarity usually belongs on the node; `causal_language` records the
authors' wording, not the strength of the evidence; null results are findings, kept as `no_relationship` edges with
`negated: true`; every node and edge is grounded in the text. `entity_term` and `measured_attribute` should be
ontology CURIEs (NCBITaxon, ENVO, PATO, ChEBI, GO, ELMO, …) where a term fits, free text otherwise. See the
[CAMO annotation essentials](https://tim-a.ca/causalmosaic/camo_annotation_essentials.html).

**Submission rules.**
- One command from a clean checkout, with pinned dependencies, run on an aarch64 Linux machine (NVIDIA DGX Spark).
- The endpoint, model and key come from `BRINE_URL`, `BRINE_MODEL` and `BRINE_API_KEY`; the model is Qwen3.8-27B on
  the shared LiteLLM endpoint.
- Output: one merged CAMO graph in YAML and JSON that passes
  `linkml-validate -s schema/causalmosaic.yaml -C CausalGraph`, with a `source_documents` entry and DOI for every
  article and every edge pointing to one of them.
- Annotation quality is judged first; footprint (energy per article, estimated mostly from LLM tokens) counts only
  once the accuracy floor is cleared. A command that fails from a clean checkout, or any schema error, halves the
  automatic score. The last commit before 6 p.m. EST on Sunday, November 15 is judged.