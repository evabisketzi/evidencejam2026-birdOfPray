"""Build data/token_counts.json.gz: the Qwen3 token count of every text that stage 1 counts on this corpus.

  PREPROCESS_TOKENIZER=/path/to/qwen3_tokenizer.json python dev/build_token_counts.py [--check]

Runs all four preprocessing modes over corpus/ with a recording counter (real Qwen tokenizer), then writes {sha1[:16]: n}.
A clean install has no `tokenizers` package; with this table it still counts (and so packs paragraph chunks) exactly like
the evaluated runs. --check: rebuild every paper's chunks with the table-only counter and compare with the Qwen chunks.
"""
import argparse, csv, gzip, json, logging, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.main import get_preprocessor                             # noqa: E402
from pipeline.preprocess.assemble import Options                       # noqa: E402
from pipeline.preprocess.legend import load_taxon_table                # noqa: E402
from pipeline.preprocess import tokens as T                            # noqa: E402

MODES = ("paragraph-chunks", "paragraph", "sentence", "sentence-chunks")


def chunks(slug, row, count, mode):
    raw = (ROOT / "corpus" / f"{slug}.md").read_text(encoding="utf-8", errors="replace")
    pre = get_preprocessor(mode)(slug, raw, row, count, Options(), load_taxon_table())
    return pre.sidecar.get("chunk_texts") or [pre.txt]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level=logging.ERROR)
    qwen, name = T.get_counter(allow_download=False)
    if not name.startswith("tokenizers:"):
        sys.exit(f"needs the real Qwen tokenizer (set PREPROCESS_TOKENIZER); got {name}")
    rows = {r["slug"]: r for r in csv.DictReader(open(ROOT / "corpus" / "index.csv", encoding="utf-8"))}
    seen = {}

    def rec(s):
        k = T.count_key(s)
        if k not in seen:
            seen[k] = qwen(s)
        return seen[k]
    ref = {(s, m): chunks(s, r, rec, m) for s, r in rows.items() for m in MODES}
    if not a.check:
        with gzip.open(T.COUNT_TABLE, "wt", encoding="utf-8") as f:
            json.dump(seen, f, separators=(",", ":"))
        print(f"wrote {T.COUNT_TABLE} ({len(seen):,} texts)")
    table = T.load_count_table()
    def table_only(s):
        n = table.get(T.count_key(s))
        return n if n is not None else T._heuristic(s)
    diff = [(s, m) for (s, m), c in ref.items() if chunks(s, rows[s], table_only, m) != c]
    print(f"table check: {len(ref) - len(diff)} of {len(ref)} (paper, mode) inputs identical to the Qwen-counted ones"
          + (f"; different: {diff[:10]}" if diff else ""))
    sys.exit(1 if diff else 0)


if __name__ == "__main__":
    main()
