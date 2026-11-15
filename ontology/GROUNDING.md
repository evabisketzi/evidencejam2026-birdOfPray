# Ontology grounding

How the free-text terms in an LLM-generated CAMO graph get ontology IDs (CURIEs), and how
to run it, from a fresh fork to a validated graph.

**Contents:** [Quick start](#quick-start) · [How it works](#how-it-works) ·
[Running it](#running-it) · [Calling it from the pipeline](#calling-it-from-the-pipeline) ·
[What's in the repo](#whats-in-the-repo) · [Rebuilding the indexes](#rebuilding-the-indexes-maintainers) ·
[Tests](#tests) · [Troubleshooting](#troubleshooting) ·
[Known limitations](#known-limitations)

## Quick start

Needs Python 3.10 or newer (tested on 3.12) and nothing else: the ontology indexes are
committed in `ontology_index/`, so there is nothing to download.

```bash
git clone <your fork> evidencejam && cd evidencejam
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt                      # ~25 s

python tests/test_grounding.py                       # ~2 s, offline; should end "ok  gold precision >= 0.9"

# Ground the demo graph and validate the result
python ground_terms.py tests/demo_graph.yaml --report report.json --out grounded.yaml
linkml-validate -s schema/causalmosaic.yaml -C CausalGraph grounded.yaml    # -> No issues found
```

`tests/demo_graph.yaml` looks like extraction output: names in every ontology field. In
`grounded.yaml`, `transplanting` has become `elmo:3621055`, `seedling` is now `PO:0007131`,
`height` is now `PATO:0000119`, and the free-text unit `ramets/m2` has moved to
`unit_text`. The input fails validation because of that unit; the output passes.

To let the LLM settle the terms the lookup could not, point it at the LiteLLM endpoint and
run the second step:

```bash
export BRINE_URL=...  BRINE_MODEL=...  BRINE_API_KEY=...
python select_terms.py report.json --graph tests/demo_graph.yaml --out grounded.yaml
```

## How it works

**The LLM never writes an ontology ID.** Extraction writes plain names; code does the
lookup; the LLM is only asked to choose between candidates the code found, by number.

```
article.md
   │  LLM extraction (names only: "Alliaria petiolata", "seeding", "height", "kg/ha")
   ▼
graph with names ──► ground_terms.py ──► report.json  +  graph with the certain IDs
                     (local lookup)         │
                                            │ ambiguous / fuzzy terms only
                                            ▼
                                     select_terms.py ──► graph with the LLM's choices
                                     (one LLM call per article; it answers "T1: 2")
```

Every term ends up in one of four states:

| Status | Meaning | What happens |
|---|---|---|
| `resolved` | Exactly one label or exact-synonym match. If several ontologies match exactly, the first one listed for that kind wins (`resolution` says so) | ID written in by `ground_terms.py` |
| `ambiguous` | Several exact matches in one ontology (homonyms, e.g. *Morus* the plant genus and *Morus* the bird genus) | LLM chooses, or keeps the text |
| `needs_review` | Only weaker matches: related/broad synonym, fuzzy, head noun ("plant biomass" → "biomass"), genus only | LLM chooses, or keeps the text |
| `no_match` | Nothing found | Free text stays, which the schema allows. Exception: `unit` only accepts `unit:`/`UO:` IDs, so its text moves to `unit_text` |

Which ontologies are searched depends on the field and on `entity_type`:

| Field | Searched in (first = preferred) |
|---|---|
| `entity_term`, `entity_type: taxon` (also `applied_to`, `counted_entity`) | NCBITaxon |
| `entity_term`, `environmental_variable` | ELMO, ENVO, ChEBI* |
| `entity_term`, `composite_variable` | ELMO, ENVO |
| `entity_term`, `environmental_process` | ELMO, GO (biological process), ENVO |
| `entity_term`, `management_intervention` | ELMO only (the annotation guide asks for this) |
| `entity_term` with no `entity_type` | ELMO, ENVO, NCBITaxon |
| `measured_attribute` | PATO (qualities), ELMO |
| `life_stage_term` | PO (plant development stages), UBERON (animal life-cycle stages) |
| `unit` | `ontology_index/units.yaml` (QUDT/UO): exact matches only, never fuzzy |

\* Only the ChEBI terms that ENVO and PATO import (988 environmental chemicals), not all of ChEBI.

Taxa use NCBITaxon, as in `example/Murphy2005.yaml` and the schema's note on
`entity_term` (the annotation guide's `wd:` advice is about the Loom tool). Abbreviations
are expanded from the document ("A. petiolata" → "Alliaria petiolata") and authorities and
`spp.` are stripped before lookup.

Values that are already CURIEs are checked, not changed: the report lists IDs that don't
exist (`not_found`) or whose label doesn't resemble the node name (`check_label`). Full
IRIs (`http://…`) are left alone.

## Running it

### 1. Ground: `ground_terms.py`

```bash
python ground_terms.py INPUT [--report report.json] [--out grounded.yaml]
```

`INPUT` is JSON or YAML: a CausalGraph, a list of nodes, or anything containing them. The
fields are found wherever they are nested.

| Option | Use |
|---|---|
| `--report FILE` | Grounding report (default `grounding_report.json`): every unique term with status, chosen ID and ranked candidates, plus checks of existing CURIEs |
| `--out FILE` | Copy of the input with the resolved IDs written in (`.yaml` or `.json`) |
| `--kinds taxon unit …` | Ground only these kinds |
| `--taxon-online` | Taxa missing from the local lexicon: ask NCBI E-utilities (cached in `ontology_index/taxon_online_cache.json`) |
| `--schema schema/causalmosaic.yaml` | Take CURIE prefixes from the schema instead of the built-in copy |
| `--top-k`, `--fuzzy-cutoff` | Candidates kept per term (10), fuzzy score threshold (80) |

It prints one line per term and a summary, e.g.
`Summary: needs_review=1, no_match=4, resolved=5; existing CURIEs: none`.

### 2. Let the LLM choose: `select_terms.py`

```bash
export BRINE_URL=https://…   BRINE_MODEL=…   BRINE_API_KEY=…   # same variables the judges set
python select_terms.py report.json --graph INPUT --out grounded.yaml
python select_terms.py report.json --dry-run      # print the prompt; no endpoint needed
```

- Only `ambiguous` and `needs_review` terms are sent. If there are none, no call is made.
- The prompt is short: per term, the node name, up to 2 excerpts, and at most 5 candidates
  (ID, label, how it matched, parents or taxon lineage, a 120-character definition). The
  model answers `{"T1": 2, "T2": 0}`, and the numbers are mapped back to IDs in code. A
  malformed or out-of-range answer counts as "none", and the text stays.
- The LiteLLM endpoint is called with a plain HTTP POST to `$BRINE_URL/chat/completions`
  (standard library only, no LLM SDK). `BRINE_URL` may end in `/v1` or not.
- Qwen's thinking mode is switched off (`chat_template_kwargs.enable_thinking=false`, plus
  `/no_think`), so the answer fits in a few tokens.
- Decisions on non-taxon terms are remembered in `ontology_index/selection_memo.json`, so a
  term such as "abundance" is asked about once per corpus. Taxa are always asked, because
  homonyms depend on the article.
- `stats:` on stderr shows calls and prompt/completion tokens, for the energy estimate.

### 3. Validate

```bash
linkml-validate -s schema/causalmosaic.yaml -C CausalGraph grounded.yaml
```

## Calling it from the pipeline

The pipeline should load the indexes once and ground each article's graph in-process (the
CLIs above are for one file at a time):

```python
from ground_terms import (CAMO_PREFIXES, EXTRACTION_RULES, Prefixes, Registry,
                          apply_groundings, ground_graph, load_config)
from select_terms import DEFAULT_MEMO, brine_llm, load_memo, save_memo, select_candidates

registry = Registry(load_config(), Prefixes(CAMO_PREFIXES))   # load the indexes once
memo = load_memo(DEFAULT_MEMO)

grounded_graphs = []
for graph in extracted_graphs:                                # one CausalGraph dict per article
    report = ground_graph(graph, registry, verbose=False)
    selections, stats = select_candidates(report, brine_llm, memo)
    grounded_graphs.append(apply_groundings(graph, report, selections))

save_memo(memo, DEFAULT_MEMO)
```

`apply_groundings` returns a copy and always moves an invalid `unit` to `unit_text`.

Put `EXTRACTION_RULES` (in `ground_terms.py`) in the extraction prompt. The lookup depends
on it: names rather than IDs, full binomials, the bare attribute in `measured_attribute`
("density", not "seedling density of Acer rubrum"), the life stage in
`life_stage`/`life_stage_term`, and `entity_type` always set, since it decides which
ontologies are searched.

## What's in the repo

| Path | What it is | Who needs it |
|---|---|---|
| `ground_terms.py` | Step 1: lookup, report, writing IDs in | everyone |
| `select_terms.py` | Step 2: LLM chooses among candidates | everyone |
| `ontology_index/*.json.gz` | Pre-built indexes: label, synonyms, short definition and parents per term (~1.7 MB in total) | everyone; **commit them** |
| `ontology_index/units.yaml` | Curated QUDT/UO units, each ID checked against QUDT 3.1.8 | everyone |
| `ontology_index/manifest.json` | Term counts and ontology versions per index | reference |
| `ontology_index/selection_memo.json` | LLM decisions, created on first use | commit it: fewer LLM calls on later runs |
| `ontology_index/taxon_online_cache.json` | NCBI answers, created by `--taxon-online` | commit it: later runs stay offline |
| `build_ontology_indexes.py` | Rebuilds `ontology_index/` from the raw ontology files | maintainers |
| `build_all.sh` | One command: environment, missing downloads, every index, tests | maintainers |
| `requirements.txt` | Runtime dependencies, pinned | everyone |
| `requirements-dev.txt` | Plus `ijson` and `oaklib`, for rebuilding | maintainers |
| `tests/test_grounding.py` | Unit tests, demo check, gold-set precision | everyone |
| `tests/grounding_gold.yaml` | Terms with their expected ID (or `null` = must not be auto-assigned) | extend it |
| `tests/demo_graph.yaml` | Small extraction-style graph used above | — |

The raw ontology files (`*-full.json`, `uberon.json`, `ncbitaxon.json`) are git-ignored:
they are large and only needed for rebuilding.

## Rebuilding the indexes (maintainers)

Rebuild when you want a newer ontology release, when the corpus changes (the NCBITaxon
lexicon only keeps taxa named in `corpus/`), or after adding a source.

Everything at once (creates `venv/` and installs `requirements-dev.txt` if needed, downloads
only the raw files missing from `raw_json/`, builds every index including NCBITaxon, runs the
tests):

```bash
./build_all.sh
git add ontology_index && git commit -m "Build ontology indexes"
```

Step by step:

```bash
pip install -r requirements-dev.txt
python build_ontology_indexes.py --download --ncbitaxon    # everything, fetching missing files
git add ontology_index && git commit -m "Rebuild ontology indexes"
```

`--download` only fetches files that aren't there yet. The taxon index is built whenever
`raw_json/ncbitaxon*.json` exists, with or without `--ncbitaxon`; the 2.4 GB file is only
downloaded with `--ncbitaxon --download`. Other forms:

```bash
python build_ontology_indexes.py                       # rebuild from files already present
python build_ontology_indexes.py --only pato elmo      # some sources only
python build_ontology_indexes.py --only ncbitaxon                                   # taxa only, raw_json/ncbitaxon.json
python build_ontology_indexes.py --only ncbitaxon --ncbitaxon /data/ncbitaxon.json   # taxa only, file elsewhere
python build_ontology_indexes.py --only ncbitaxon --ncbitaxon --download             # taxa only, fetch the file
python build_ontology_indexes.py --ncbitaxon /data/ncbitaxon.json --corpus other_articles/
python build_ontology_indexes.py --ncbitaxon --extra-taxa "Canis lupus"   # keep extra names
```

The raw ontology files (`*-full.json`, `uberon.json`, `ncbitaxon.json`) go in `raw_json/` at
the repo root, the folder that holds `corpus/`. Subfolders of `raw_json/` are searched too,
and `--download` saves there. The script finds `raw_json/` and `corpus/` whether it sits at
the repo root or one folder below it; `--src-dir` and `--corpus` override that. If the corpus folder has no
`*.md` articles, it stops before downloading or reading NCBITaxon (it would otherwise build
an empty taxon index).

| Index | Read from | Download | Kept |
|---|---|---|---|
| elmo | `elmo-full.json` ← raw.githubusercontent.com/timalamenciak/elmo/main/elmo-full.json | 1 MB | `elmo:` and `elmo_cas:` terms |
| envo | `envo-full.json` ← purl.obolibrary.org/obo/envo.json | 7 MB | `ENVO:` terms |
| go | `go-full.json` ← purl.obolibrary.org/obo/go.json | 83 MB | biological process branch |
| pato | `pato-full.json` ← purl.obolibrary.org/obo/pato.json | 13 MB | quality branch |
| chebi | the CHEBI terms imported into envo and pato | — | 988 terms |
| uberon | `uberon.json` ← purl.obolibrary.org/obo/uberon.json | 55 MB | life cycle stage branch |
| po | OAK `sqlite:obo:po` (PO publishes no JSON), cached in `~/.data/oaklib` | 4.6 MB | plant development stages |
| ncbitaxon | `ncbitaxon.json` ← purl.obolibrary.org/obo/ncbitaxon.json | 2.4 GB | taxa named in `corpus/`, plus their lineage |

Without NCBITaxon, the build takes about 20 seconds plus downloads. For NCBITaxon, the file
is streamed twice with `ijson`: once for names, once for `is_a` edges. Every taxon's label
and parent are held in memory, so allow a few GB of RAM. Names are matched against 1–4-word
sequences from `corpus/*.md`. The result should be a few thousand taxa and under 2 MB. On
the full 2.4 GB file this path hasn't been timed yet; it was tested on a small file of the
same shape.

The build reads the JSON directly rather than through OAK's JSON adapter. That adapter took
over 10 minutes for 3,000 GO terms, and it crashes on terms without metadata. OAK is used
only where it is fast (the SQLite build of PO).

### Adding an ontology

To make a new ontology permanent, add it to `SOURCES` in `build_ontology_indexes.py`
(JSON file or OAK adapter, CAMO prefixes, optional `roots` branch and `strip_suffixes`),
rebuild, add it to `DEFAULT_CONFIG` in `ground_terms.py`, and commit the index.

`strip_suffixes` lets people's words match labels that carry a suffix: ELMO's
"seeding process" also matches "seeding", PO's "seedling development stage" also matches
"seedling", and UBERON's "larval stage" also matches "larval".

## Tests

```bash
python tests/test_grounding.py              # unit tests, demo graph, gold-set precision (offline)
python tests/test_grounding.py --with-llm   # also lets the LLM settle the pending gold terms
```

The gold check prints precision and recall for automatic assignments (and, with
`--with-llm`, for automatic plus LLM choices) against `tests/grounding_gold.yaml`, and
fails below 0.9 precision. Entries with `expect: null` must *not* be assigned
automatically, e.g. `abundance`: PATO's nearest term, PATO:0000070, is "amount".
Taxon entries are skipped until the NCBITaxon index exists. Add hand-checked terms from
corpus articles as you find them; the current set was assembled from checked ontology
labels, so it guards against regressions rather than measuring real-world accuracy.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `WARNING: index ontology_index/ncbitaxon.json.gz not built` | Taxa stay free text. Put `ncbitaxon.json` in `raw_json/`, run `python build_ontology_indexes.py --only ncbitaxon` (or `--only ncbitaxon --ncbitaxon --download`), and commit `ontology_index/ncbitaxon.json.gz` |
| `set BRINE_URL, BRINE_MODEL, BRINE_API_KEY (or use --dry-run)` | Export the three variables |
| `WARNING: could not parse LLM reply (length)` | The model ran out of tokens, usually because it is "thinking". Check that the LiteLLM endpoint honours `chat_template_kwargs` / `/no_think`. The affected terms keep their text. If LiteLLM rejects `chat_template_kwargs` (HTTP 400), the script drops it and relies on `/no_think` |
| `WARNING: LLM call failed (HTTP 401 from LiteLLM: …)` | Wrong or missing `BRINE_API_KEY` |
| `WARNING: LLM call failed (HTTP 404 from LiteLLM: …)` | `BRINE_URL` should be the proxy's base URL (with or without `/v1`), not another route |
| `WARNING: LLM call failed` | Endpoint unreachable. The affected terms keep their text and the run continues |
| linkml error on `unit` | A `unit` value that isn't `unit:`/`UO:`. Use the graph written by `--out` / `apply_groundings`, which moves it to `unit_text` |
| Too many `needs_review` terms | The extraction wrote long phrases. Check that `EXTRACTION_RULES` is in its prompt |
| A wrong ID was assigned | Add the term to `tests/grounding_gold.yaml` with the right ID (or `null`) and look at its candidates in the report |

## Known limitations

- **The NCBITaxon index isn't built yet**, so taxa stay free text until a maintainer runs the
  build with `--ncbitaxon` and commits `ontology_index/ncbitaxon.json.gz`.
- **PATO has no "abundance", "cover" or "survival".** These measured attributes stay free
  text unless ELMO has a matching variable.
- **Exact synonyms are trusted.** Some of ELMO's are loose: "succession" resolves to
  "succession stage", and "competition" to "competition intensity".
- **The LLM step has been tested against a stand-in, not the live endpoint.** Run
  `tests/test_grounding.py --with-llm` once credentials are available.
