# Evidence Jam 2026 — Lane 1: Causal Annotation

## Our submission

```
./run.sh corpus/ output/
```

Set `BRINE_URL`, `BRINE_MODEL` and `BRINE_API_KEY` first. The command creates its own virtual environment from the
pinned `requirements.txt` and writes one merged CAMO graph to `output/camo_graph.yaml` and `output/camo_graph.json`,
validated against `schema/causalmosaic.yaml`.

How it works: code selects and numbers the text worth annotating, the model writes one short line per causal claim,
and code turns those lines into CAMO nodes and edges, attaches ontology IDs, and repairs or drops anything the schema
would reject. The model never writes YAML or IDs.

| read this | for |
|---|---|
| [reports/METHOD.md](reports/METHOD.md) | the pipeline, stage by stage, and how we evaluate |
| [reports/RESULTS.md](reports/RESULTS.md) | the numbers behind the submitted configuration, and what is not measured |
| [dev/experiments/LOG.md](dev/experiments/LOG.md) | every experiment, kept or not |

The rest of this file is the organisers' original description of the challenge.

## The challenge

> **Create a script that annotates the scientific journal articles, contained in**
> **`corpus/` in markdown format, using the Causal Mosaic Schema (CAMO). The annotations**
> **should be in YAML and JSON. Use ontologies where-ever possible.**

Your script should read the articles in `corpus/` and produce one merged CAMO
graph, in both YAML and JSON, that validates against
`schema/causalmosaic.yaml`: the causal claims the authors make, what they are
claims *about*, how strongly they make them, and where in the text they make
them. You do not need to annotate every single article (there may not be time). 
Points will be awarded based on the quality of the annotations.

## What's in this repo

```
corpus/              308 ecological restoration articles, one markdown file each
corpus/index.csv     slug, DOI, title, authors, year, journal, word count
example/             hand-checked CAMO annotation of one article
schema/              the Causal Mosaic Schema (CAMO) v0.10.0, as LinkML
```

### `corpus/`

Each article is named by a short slug (e.g. `YKQQZV93.md`) and was converted
from PDF, so expect conversion artefacts: image placeholders, broken tables,
headers and footers mid-paragraph, and inline tags. Use
`corpus/index.csv` to look up an article's DOI and bibliographic details.

### `example/`

Worked annotation showing what good output looks like: `Murphy2005.yaml`
and its source: `Murphy2005.pdf`

### `schema/causalmosaic.yaml`

The Causal Mosaic Schema is a way of describing causal relationships between 
populations of taxa, environmental variables, composite variables, management
interventions and environmental processes. The header comments and
the `description` on every class, slot, and enum are the annotation guide.

There's an annotation essentials guide here: https://tim-a.ca/causalmosaic/camo_annotation_essentials.html

## How a CAMO graph works

A `CausalGraph` has `nodes`, `edges`, `provenance`, and `source_documents`.

**A node is a state, not a thing.** A taxon doesn't cause anything by itself.
A node is a *state or change of an attribute of an entity*, split into three
fields:

```yaml
- id: node:murphy2005_alliaria_population_performance
  name: Decreased population performance of Alliaria petiolata
  entity_type: taxon
  entity_term: Alliaria petiolata        # ideally an ontology CURIE (see below)
  measured_attribute: population performance
  state_or_change_qualifier: decreased
  source_spans:
  - text: initial S. canadensis densities of as little as 5 ramets/m2 suppressed A. petiolata
```

**An edge is a causal claim** between two nodes, carrying a controlled
`predicate` (`causes`, `contributes_to`, `prevents`, `associated_with`, …), the
authors' `causal_language` (`direct_causal`, `uncertain_causal`,
`associational`, `no_relationship`), the `original_sentence`, and optional
causal-feature annotations (direction, mediation, moderation, strength,
necessity/sufficiency, one `comparator` entry per comparison arm, evidential
basis, …).

Four things to get right:

- **Polarity usually belongs on the node, not the predicate.**
  `causes → "Decreased weed cover"` is a negative effect.
- **`causal_language` records the authors' language, not how strong the
  evidence is.** A paper can make strong claims on weak evidence; how strong
  the evidence is goes in `certainty_grade`.
- **Null results are findings.** "No significant effect" is an edge with
  `causal_language: no_relationship` and `negated: true`, always both. The
  object node is the variable that was tested, with the qualifier a positive
  finding would use. `unchanged` means a measured stable state, never a null
  result. Don't drop null results.
- **Ground every node and edge in the text** with `source_spans` and
  `original_sentence`.

## Use ontologies where possible

`entity_term` and `measured_attribute` accept either an ontology CURIE or free
text. Prefer the CURIE, and fall back to free text only when no term fits:

| What | Ontology | Example |
| --- | --- | --- |
| Taxa | NCBITaxon | `NCBITaxon:3472` (*Sanguinaria canadensis*) |
| Environments, habitats, abiotic factors | ENVO | `ENVO:01000253` (grassland) |
| Qualities / measured attributes | PATO | `PATO:0000070` (abundance), `PATO:0000574` (density) |
| Chemicals | ChEBI | `CHEBI:24279` (glucosinolate) |
| Biological processes and rates | GO | `GO:0008150` |
| Ecosystem functional groups | ELMO | `ELMO:3620100` … (see `EcosystemFunctionalGroupEnum`) |
| Evidence types | ECO | |
| Occurrence and sampling fields | Darwin Core / Humboldt | `dwc:`, `tdwgeco:` |

The full prefix map is in the `prefixes:` block at the top of the schema. Use
`applied_to` to scope a node to the taxa or guilds it aggregates over, or to
name the target of a process or intervention.

## Validating your output

The schema is LinkML, so you can validate with the stock LinkML tooling:

```bash
pip install linkml
linkml-validate -s schema/causalmosaic.yaml -C CausalGraph my_output.yaml
```

Run this on the files in `example/` first to see what a passing graph looks
like.

## Getting started

```python
import csv, yaml
from pathlib import Path

index = {row["slug"]: row for row in csv.DictReader(open("corpus/index.csv", encoding="utf-8"))}
schema = yaml.safe_load(open("schema/causalmosaic.yaml", encoding="utf-8"))
example = yaml.safe_load(open("example/Murphy2005.yaml", encoding="utf-8"))

for path in sorted(Path("corpus").glob("*.md")):
    text = path.read_text(encoding="utf-8")
    meta = index[path.stem]
    # ... your extractor: text -> CausalGraph ...
```

## Submitting

The last commit before **6 p.m. EST on Sunday, November 15** will be used for judging.

Judges run every submission on one machine, one at a time: an NVIDIA DGX Spark
(GB10, **ARM64 / aarch64** Linux, CUDA). The LLM is Qwen3.8-27B on the shared
LiteLLM endpoint, the same endpoint and model you use during development, so
what works for you will work for the judges.

1. **One command, from a clean checkout.** Your README should give a single
   command that runs the whole pipeline, for example
   `./run.sh corpus/ output/`, reading the articles in `corpus/`. Pin your
   dependencies (a lock file or `==` versions).
2. **Read the LLM endpoint, model and key from the environment.** Use exactly
   these variables: `BRINE_URL` (the endpoint URL), `BRINE_MODEL` (the model
   name) and `BRINE_API_KEY` (your key). Judges set the same three to run you
   with their own key on the same endpoint. Don't hardcode any of them, and
   don't commit keys.
3. **Output.** One fully merged CAMO graph, in both YAML and JSON. It must
   validate against `schema/causalmosaic.yaml` and carry a `source_documents`
   entry for every article, with each article's DOI from `corpus/index.csv`.
   Every edge's `source_document` must point to one of those entries.

Footprint is energy (Wh) per article: what your code uses on the judging
machine plus the model's share, estimated from the tokens your run uses on the
LiteLLM endpoint. It's ranked against the other teams, and it only counts once your submission clears the lane's
accuracy floor. A command that doesn't run from a clean checkout, or a graph
with any schema validation errors, halves your automatic scores until it is
fixed.
