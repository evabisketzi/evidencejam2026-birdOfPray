"""Print each model input (chunk) of a paper and the CACHED answer for it, or the answers saved in a job directory.

  python dev/show_io.py SLUG [--preprocess paragraph-chunks] [--prompt system.txt] [--job dev/jobs/out/JOB] [--grep WORD]
"""
import argparse, json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
for k, v in (("BRINE_URL", "http://127.0.0.1:9/v1"), ("BRINE_MODEL", "Qwen3.8-27B"), ("BRINE_API_KEY", "unused")):
    os.environ.setdefault(k, v)


def chunks_for(slug, preprocess="paragraph-chunks", opts=None):
    import csv
    from pipeline.main import get_preprocessor
    from pipeline.preprocess.assemble import Options
    from pipeline.preprocess.legend import load_taxon_table
    from pipeline.preprocess.tokens import get_counter
    from pipeline.extract import split_user_text
    rows = {r["slug"]: r for r in csv.DictReader(open(ROOT / "corpus/index.csv", encoding="utf-8"))}
    count, _ = get_counter(allow_download=False)
    raw = (ROOT / f"corpus/{slug}.md").read_text(encoding="utf-8", errors="replace")
    pre = get_preprocessor(preprocess)(slug, raw, rows[slug], count, opts or Options(), load_taxon_table())
    return pre, pre.sidecar.get("chunk_texts") or split_user_text(pre.txt, 12000)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--preprocess", default="paragraph-chunks")
    ap.add_argument("--prompt", default="system.txt")
    ap.add_argument("--job")
    ap.add_argument("--grep", help="only chunks whose input contains this text")
    ap.add_argument("--no-input", action="store_true")
    a = ap.parse_args()
    from pipeline.extract import Client, config_from_env, load_prompt
    _, system = load_prompt(a.prompt)
    pre, chunks = chunks_for(a.slug, a.preprocess)
    saved = None
    if a.job:
        for line in open(Path(a.job) / "raw_responses.jsonl", encoding="utf-8"):
            d = json.loads(line)
            if d["doc"] == a.slug:
                saved = d["responses"]
    cfg = config_from_env(False, True, 3000)
    cl = Client(cfg)
    for i, ch in enumerate(chunks):
        if a.grep and a.grep not in ch:
            continue
        print(f"===== chunk {i + 1}/{len(chunks)} INPUT =====")
        if not a.no_input:
            print(ch)
        if saved is not None:
            ans = saved[i] if i < len(saved) else "(none saved)"
        else:
            cp = cl._cache_path(system, ch, False)
            ans = json.loads(cp.read_text())["text"] if cp.exists() else "(not cached)"
        print(f"----- chunk {i + 1} ANSWER -----")
        print(ans)


if __name__ == "__main__":
    main()
