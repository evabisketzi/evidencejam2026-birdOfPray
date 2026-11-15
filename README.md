# Evidence Jam 2026 — Lane 1: Causal Annotation

Turns the 308 ecological restoration articles in `corpus/` into one merged causal graph in the Causal Mosaic Schema
(CAMO v0.10.0), as YAML and JSON, validated against the schema. A language model reads; plain code writes the graph.

**Contents:** [Setup](#setup) · [How it works](#how-it-works) · [Outputs](#outputs) · [Options](#options) ·
[Results and cost](#results-and-cost) · [Repository structure](#repository-structure) · [Development](#development) ·
[Troubleshooting](#troubleshooting) · [Documentation](#documentation) · [Acknowledgements](#acknowledgements) ·
[The challenge](#the-challenge)

## Setup

**Requirements**
- Linux (x86-64 or aarch64)
- Python 3 with `venv`, tested on 3.12 (Debian/Ubuntu: `sudo apt install python3-venv`)
- Internet access on the first run (to install the pinned dependencies)
- Access to the BRINE endpoint: URL, model name and key

**1. Clone**

```bash
git clone https://github.com/evabisketzi/evidencejam2026-birdOfPray.git
cd evidencejam2026-birdOfPray
```

**2. Set the endpoint** (environment only; never commit the key)

```bash
export BRINE_URL=...        # endpoint URL, with or without /v1
export BRINE_MODEL=...      # model name
export BRINE_API_KEY=...    # your key
```

**3. Run**

```bash
./run.sh corpus/ output/
```

The result is `output/camo_graph.yaml` and `output/camo_graph.json`. The first run builds `.venv/` from
`requirements.txt`. A full run takes about 4 h 40 min; rerunning on unchanged input takes minutes (cached answers).

**No key?** Check the plumbing against the bundled fake endpoint (needs Python 3.12+; the graph it produces means
nothing):

```bash
python3 dev/mock_endpoint.py 18999 &
BRINE_URL=http://127.0.0.1:18999/v1 BRINE_MODEL=mock BRINE_API_KEY=mock ./run.sh corpus/ out_mock/ --limit 5 --no-cache
kill %1
```

## How it works

The model reads, the code writes.

1. **Select the text.** Code cleans each converted article, drops the introduction, methods and references, keeps the
   paragraphs with causal cue words, numbers their sentences and lists the species as short codes (`T1`, `T2`, …).
   One model call per chunk of at most 2,500 tokens.
2. **Extract.** The model (Qwen on the BRINE endpoint) writes one short line per causal claim the authors make about
   their own study. It never writes YAML, IDs or character offsets, so it cannot produce an invalid graph, and its
   answers stay short.
3. **Build the graph.** Code turns each line into CAMO nodes (entity, measured attribute, state or change) and edges
   (predicate, the authors' causal language, conditions), with the original sentence and its character span. Null
   results become `no_relationship` edges with `negated: true`; hedged sentences are labelled uncertain.
4. **Use ontologies.** Species get NCBITaxon IDs from a table built from the NCBI taxonomy. Other entities, measured
   attributes and life stages get ENVO, PATO, GO, ChEBI, PO, UBERON or ELMO IDs from committed ontology indexes, but
   only when exactly one label or exact synonym matches. Anything ambiguous stays free text, because a wrong ID is
   worse than none.
5. **Guard and validate.** Code repairs or drops anything the schema would reject and removes repeated claims. Every
   `corpus/index.csv` row gets a `source_documents` entry with its DOI, even when extraction failed for that paper.
   One failing paper never stops the run.

One claim as the model writes it (the format is defined in `pipeline/prompt/system.txt`):

```
F|12|T1/initial planting density/+/tax|c|T2/number of individuals/-|D|exp|stage=seedling|dose=9-11 ramets/m2
```

| field | meaning |
|---|---|
| `F` | a finding (`N` = a null result: "no significant effect") |
| `12` | the sentence number(s) the claim comes from; code turns them into the source span and `original_sentence` |
| `T1/initial planting density/+/tax` | cause: entity (species code) / measured attribute / change (`+`, `-`) / entity type |
| `c` | predicate (`c` = causes) |
| `T2/number of individuals/-` | effect (several effects are separated by `;`) |
| `D` | the authors' causal language: `D` direct, `U` uncertain (hedged), `A` associational |
| `exp` | study design (experimental, observational, …) |
| `stage=…`, `dose=…` | optional conditions: life stage, dose, comparison, season, mediator, … |

Stage by stage: [reports/METHOD.md](reports/METHOD.md). Ontology grounding: [ontology/GROUNDING.md](ontology/GROUNDING.md).

## Outputs

Everything goes into the output directory given to `run.sh`.

| file | contents |
|---|---|
| `camo_graph.yaml`, `camo_graph.json` | **the result**: one merged CAMO graph (nodes, edges, provenance, source_documents) |
| `tokens.csv` | per paper: prompt and completion tokens, seconds, number of chunks |
| `run_log.json` | the settings used, and per-paper counts and errors |
| `raw_responses.jsonl` | every model answer, in call order (`dev/replay.py` rebuilds the graph from it without the endpoint) |
| `losses.jsonl` | claim lines lost before the graph (unparseable, unknown sentence, failed paper) and why |
| `retries.csv` | endpoint calls that were retried |
| `doi_report.csv` | the DOI used for each paper and where it came from |
| `ontology_report.json` | each term the ontology stage looked up: status (resolved, needs review, no match), ID, candidates |

- **Re-validate by hand:** `.venv/bin/python -m pipeline.validate output/`, or
  `.venv/bin/linkml-validate -s schema/causalmosaic.yaml -C CausalGraph output/camo_graph.yaml`.
- **Cache:** model answers are stored in `.cache/extract/`, keyed by model + prompt + input + `--max-tokens`. Delete the
  folder to start fresh.

## Options

`./run.sh CORPUS_DIR OUTPUT_DIR [options]`. The defaults are the submitted configuration.

```bash
./run.sh corpus/ out/ --docs YKQQZV93     # one paper (YKQQZV93 = Murphy 2005, the organisers' example)
./run.sh corpus/ out/ --limit 10          # the first 10 papers of index.csv
./run.sh corpus/ out/ --smoke YKQQZV93    # one uncached call: tokens, speed and parse stats (saved in dev/out/)
```

| option | default | what it does |
|---|---|---|
| `--docs A,B` / `--limit N` | all | only these papers / the first N |
| `--concurrency N` | 4 | parallel model calls |
| `--preprocess` | `paragraph-chunks` | text selection: `paragraph-chunks` (one call per chunk), `paragraph` (one call per paper), `sentence` / `sentence-chunks` (sentence filter) |
| `--ontology` | `lookup` | `lookup` (exact matches only, no model call), `select` (the model picks among candidates, one short call per paper), `off` |
| `--prompt FILE` | `system.txt` | a prompt from `pipeline/prompt/` |
| `--max-tokens N` | 3000 | output limit per call |
| `--thinking on/off` | off | the model's reasoning mode (more tokens; not used) |
| `--refresh-cache` / `--no-cache` | | call the model again and store the new answer / neither read nor write the cache |
| `-v` | | verbose log |

Full list: `.venv/bin/python -m pipeline.main --help`. Experimental flags that are off by default are described in
[reports/RESULTS.md](reports/RESULTS.md#options-that-exist-but-are-off-by-default).

## Results and cost

Measured with our own scorer against our reference annotations. This is not the judges' score; details are in
[reports/RESULTS.md](reports/RESULTS.md).

- **Murphy 2005** (the organisers' worked example, the only human reference): standard F1 0.579 over 3 runs
  (range 0.575–0.583), strict F1 0.518, null-result recall 0.71.
- **Full corpus:** 308 papers, 0 failed, 30,208 edges, schema-valid.
- **Tokens:** about 9,300 prompt and 2,300 completion tokens per article (about 3.6 M in all). Answers are cached, so
  an unchanged input is never sent twice.
- **Limitations:** on the 7 reference papers Claude annotated, standard F1 is only about 0.17. The reference set is
  small, and only Murphy is human-made. The ontology step (no model call, so no extra tokens) was switched on after
  these measurements. On another pipeline's graphs it left Murphy unchanged and lowered out-of-sample F1 by 0.011,
  which that analysis attributes to our scorer not knowing ELMO, ENVO and GO labels. On our own output it is not
  measured.

## Repository structure

| path | what it is |
|---|---|
| `run.sh` | the one command: checks the environment, builds `.venv/`, runs the pipeline |
| `requirements.txt`, `requirements-dev.txt` | pinned runtime dependencies; test and development dependencies |
| `pipeline/` | the pipeline; `main.py` is the entry point, `prompt/` holds the prompts |
| `data/` | lookup tables: `ncbitaxon_names.tsv` (species → NCBITaxon), `terms.tsv` (verified term IDs), `taxon_groups.tsv`, `camo.schema.json` (JSON Schema generated from CAMO), `token_counts.json.gz` (precomputed Qwen token counts) |
| `ontology/` | ontology grounding: `ground_terms.py`, `select_terms.py`, the committed indexes in `ontology_index/`, and the scripts to rebuild them ([GROUNDING.md](ontology/GROUNDING.md)) |
| `corpus/` | the 308 articles and `index.csv` (given; never modified) |
| `schema/` | CAMO v0.10.0 as LinkML (given; never modified) |
| `example/` | the organisers' worked annotation, Murphy 2005 (YAML + PDF) |
| `tests/` | unit and end-to-end tests (`pytest`) |
| `dev/` | development tools: scorer (`score/`), gold annotations (`gold/`), evaluation, replay, job runner, mock endpoint, preflight, experiment log (`experiments/LOG.md`), diagnostics (`diag/`) |
| `reports/` | `METHOD.md` (design), `RESULTS.md` (numbers), older reports |
| `scripts/` | `build_taxon_table.py`, which rebuilds `data/ncbitaxon_names.tsv` |
| `preprocess_paper.py`, `preprocess_corpus.py` | a teammate's standalone paragraph preprocessor (no LLM, standard library only); the pipeline uses a verbatim copy, `pipeline/preprocess/team_paper.py` |
| `grounded.yaml` | demo output of `ontology/ground_terms.py` on `ontology/tests/demo_graph.yaml` |
| `.claude/` | Claude Code project setup: hooks (block secrets and edits to protected files, run fast tests), skills `/experiment` and `/preflight`, agent `error-analyst` |
| `CLAUDE.md` | working rules for Claude Code in this repo (also a good summary for humans) |

## Development

```bash
.venv/bin/python -m pip install -r requirements-dev.txt            # after one ./run.sh, which creates .venv
.venv/bin/python -m pytest -q tests                                # full suite, about 1–1.5 min, no endpoint needed
.venv/bin/python dev/eval_murphy.py out/camo_graph.yaml --others   # score a graph on Murphy and the other gold papers
.venv/bin/python dev/eval_murphy.py --cached --others              # rerun cached model answers through the current code
.venv/bin/python dev/replay.py dev/jobs/out/JOB OUT.yaml           # rebuild a past run's graph with the current code
dev/preflight.sh                                                   # clean-checkout check before pushing a submission
```

- **Gold annotations** (`dev/gold/`): 8 papers. `murphy2005.yaml` (paper `YKQQZV93`) is the organisers' human
  annotation and the main yardstick; the other 7 were made with Claude. The scorer (`dev/score/`) matches edges at three
  levels: *loose* (same cause and effect entities), *standard* (plus a similar measured attribute and no opposite
  direction), *strict* (plus the same direction).
- **Code after the model changed** (parse, expand, guard, write): compare exactly with `--cached` or `dev/replay.py`.
- **Prompt or preprocessing changed:** identical endpoint runs differ by about ±0.04 in Murphy standard F1, so run
  each variant at least 3 times and compare means and ranges.
- **Background endpoint runs:** in a shell with the three `BRINE_*` variables, start
  `tmux new -d -s jobs 'dev/jobrunner.sh'`, then queue a run by writing one line such as
  `preprocess=paragraph-chunks set=gold8 cache=off` to `dev/jobs/queue/NAME.job`. Output goes to `dev/jobs/out/NAME/`;
  the accepted keys are listed at the top of `dev/jobrunner.sh`.
- **Log every experiment** in `dev/experiments/LOG.md`, kept or not.
- **Rules:** never commit or print the API key (`.env` is git-ignored; hooks block key-like strings). Never edit
  `corpus/`, `schema/`, `dev/gold/` or `data/camo.schema.json`. Keep `./run.sh corpus/ output/` working from a clean
  checkout.

## Troubleshooting

| symptom | cause and fix |
|---|---|
| `error: missing environment variable(s): BRINE_...` (exit 2) | export all three `BRINE_*` variables in the same shell |
| `The virtual environment was not created successfully` | install `python3-venv` (Debian/Ubuntu), or set `PYTHON=` to a Python that has `venv` |
| `pip install` fails | the first run needs internet access to PyPI; dependencies are pinned in `requirements.txt` |
| HTTP 404 from the endpoint | check `BRINE_URL`; it works with or without `/v1` (the client adds `/chat/completions`) |
| a paper is missing claims | look it up in `losses.jsonl` and `run_log.json`; it still gets its `source_documents` entry |
| `no edges at all: extraction failed for every document` | every call failed (endpoint down, wrong model name or key): `--smoke YKQQZV93` shows one raw call; `retries.csv` lists the errors |
| you want a fresh answer for unchanged input | `--refresh-cache`; otherwise the cache returns the stored answer |

## Documentation

| read this | for |
|---|---|
| [reports/METHOD.md](reports/METHOD.md) | the pipeline, stage by stage, and how we evaluate |
| [reports/RESULTS.md](reports/RESULTS.md) | the numbers behind the submitted configuration, and what is not measured |
| [ontology/GROUNDING.md](ontology/GROUNDING.md) | how terms get ontology IDs, and how the indexes are built |
| [dev/experiments/LOG.md](dev/experiments/LOG.md) | every experiment, kept or not |

## Acknowledgements

Thanks to the Evidence Jam 2026 organisers for running the hackathon and for the corpus, the Causal Mosaic Schema, the
hand-checked Murphy 2005 annotation and the shared model endpoint.

Team: evabisketzi, lilac-haze, lorelyai. We used Claude Code (Anthropic) during development.

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
