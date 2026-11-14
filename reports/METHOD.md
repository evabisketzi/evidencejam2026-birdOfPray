# Method

One command turns the 308 articles in `corpus/` into one merged CAMO v0.10.0 graph, in YAML and JSON:

```
./run.sh corpus/ output/
```

It needs `BRINE_URL`, `BRINE_MODEL` and `BRINE_API_KEY` in the environment. It writes `output/camo_graph.yaml` and
`output/camo_graph.json`, plus `tokens.csv`, `run_log.json`, `retries.csv` and `doi_report.csv`.

## Design in one paragraph

The language model (Qwen on the shared endpoint) does one thing only: it reads a shortened, numbered version of a paper
and writes one short line per causal claim. Everything else is ordinary code: choosing which text the model sees,
turning each line into CAMO nodes and edges, attaching ontology IDs, repairing or dropping anything the schema would
reject, and validating the result. The model never writes YAML, IDs or character offsets, so it cannot produce an
invalid graph, and its output stays short, which keeps the token cost per article low.

## The six stages (`pipeline/`)

| # | stage | code | what it does |
|---|---|---|---|
| 1 | Preprocess | `preprocess/` | Selects the text worth annotating and numbers its sentences. Each sentence keeps its character offsets in the original markdown. |
| 2 | Grounding | `grounding.py`, `data/` | Looks up NCBITaxon IDs for species names and ontology IDs for a small table of verified terms. |
| 3 | Extraction | `extract.py`, `prompt/system.txt` | One model call per chunk of the paper. The answer is one line per claim. |
| 4 | Parse and expand | `parse.py`, `expand.py` | Reads the lines and builds CAMO nodes and edges from them. |
| 5 | Guard and merge | `guard.py` | Repairs or drops anything invalid, removes repeated claims, merges all papers into one graph. |
| 6 | Write and validate | `write.py`, `validate.py` | Writes YAML and JSON and validates both against the schema. |

### 1. Preprocess

The default (`--preprocess paragraph-chunks`) uses the paragraph selection in `preprocess/team_paper.py`
(the same file as `preprocess_paper.py` at the repository root). It cleans the converted markdown, drops the
introduction, methods and reference list, scores the remaining paragraphs by cue words and keeps those above a
threshold. The kept paragraphs are packed into chunks of at most 2,500 tokens, and each chunk is one model call.

Every call starts with the same header:

- `TITLE`: the article title.
- `SPECIES`: a legend of the species the paper names, as short codes (`T1=Sanguinaria canadensis (S. canadensis)`).
  The model answers with the code, and the code is turned back into the name and its NCBITaxon ID afterwards.
- `CONTEXT`: up to 400 tokens of the paper's aims and study design, marked as background that must not be annotated.

Three other stage-1 modes are kept for comparison: `paragraph` (the same selection, whole paper in one call),
`sentence` (our own sentence filter: split into sentences, drop sentences that only report other studies, shorten
statistics) and `sentence-chunks` (the sentence filter with one call per chunk).

If the paragraph selection fails on a paper, that paper falls back to the sentence filter, so no paper is lost.

### 2. Grounding

- Taxa: `data/ncbitaxon_names.tsv` maps scientific names to NCBITaxon IDs (exact match, then case-insensitive, then
  genus and epithet without the authority).
- Other terms: `data/terms.tsv`. Only rows a person has marked as verified ever produce an ID. Everything else stays
  free text, because a wrong ID is worse than none.

### 3. Extraction

The prompt (`pipeline/prompt/system.txt`) asks for one line per claim the authors make about their own study:

```
F|12|T1/initial planting density/+/tax|c|T2/number of individuals/-;T2/height/-|D|exp|stage=seedling|dose=9-11 ramets/m2
N|19|T1/initial planting density/+/tax|c|T2/number of individuals|exp|stage=seedling|season=early_spring
```

A line gives the sentence numbers, the cause, the predicate, one or more effects, the causal language (direct, hedged
or associational) and the study design, with optional keys for life stage, dose, comparison, season, mediator and
conditions. `N` lines are null results. If some lines cannot be parsed, the model gets one repair call for those lines.

Answers are cached in `.cache/extract/` by model, prompt, input and token limit, so an unchanged input never costs
tokens twice.

### 4. Parse and expand

Each cause and effect becomes a CAMO node (entity, measured attribute, state or change). Each line becomes one edge
per effect, with the predicate, causal language, the original sentence and its source span taken from the sentence
numbers. A mediator becomes its own node with two path edges. A null result becomes an edge with
`causal_language: no_relationship` and `negated: true`.

Three rule-based corrections are applied here:

- A "direct" claim whose sentence is hedged (may, might, could, appears, suggests) becomes "uncertain".
- Node names are composed so that they read naturally ("Establishment of X", not "Presence of establishment of X").
- Abbreviations the paper defines are written out in node names ("Soil volumetric moisture content (VMC)").

### 5. Guard and merge

Every node and edge is checked against the schema's rules. An invalid optional field is dropped and the edge kept; an
edge with a broken required field is dropped. A claim repeated within the same sentence is kept once. Then all papers
are merged. Every row of `corpus/index.csv` gets a `source_documents` entry with its DOI, including papers where
extraction failed, and every edge points to one of those entries.

### 6. Write and validate

The graph is written as YAML and JSON and validated twice: against a JSON Schema generated from the CAMO schema, and
with `linkml-validate -s schema/causalmosaic.yaml -C CausalGraph`. One failing paper never stops the run. If no paper
produces an edge, the run fails loudly instead of writing an empty graph.

## How we evaluate

- **Gold papers:** five, in `dev/gold/`. `murphy2005.yaml` is the organisers' example and the main yardstick. The other
  four are team annotations, used as an out-of-sample check.
- **Scorer:** `dev/score/`, three levels. *Loose*: the cause and effect entities agree, and both edges are null results
  or both are not. *Standard*: loose, plus the measured attribute of the effect is similar (at least 0.5) and the
  directions of change are not opposite. *Strict*: standard, plus the same direction of change.
- **Changes to the code after the model** (stages 4 to 6) are compared exactly, on cached model output.
- **Changes to the prompt or the preprocessing** are compared with at least 3 endpoint runs per variant, because
  identical runs differ by about ±0.04 in Murphy standard F1.
- Every experiment, kept or not, is in `dev/experiments/LOG.md`. Results are summarised in `reports/RESULTS.md`.

## Development tools (`dev/`)

| file | purpose |
|---|---|
| `eval_murphy.py` | Scores a graph, or the cached model output, on the gold papers. |
| `jobrunner.sh` | Runs queued endpoint jobs, two at a time. |
| `preflight.sh` | Checks that a commit runs from a clean checkout against a mock endpoint. |
| `mock_endpoint.py` | A fake endpoint for plumbing tests. |
| `diag/` | One-off diagnostics behind the decisions in the log. |
