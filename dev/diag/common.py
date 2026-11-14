"""Shared helpers for the diagnosis scripts (read-only; no LLM calls: extraction comes from the cache)."""
import csv, json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("BRINE_URL", "http://unused.invalid/v1"); os.environ.setdefault("BRINE_MODEL", "Qwen3.8-27B"); os.environ.setdefault("BRINE_API_KEY", "unused")
from pipeline.extract import Client, config_from_env, load_prompt, extract_paper, LLMError
from pipeline.preprocess.assemble import Options, process_paper
from pipeline.preprocess.legend import load_taxon_table
from pipeline.preprocess.tokens import get_counter

RUN = ROOT / "dev/overnight/20261113_202118"

def pre_for(slug):
    corpus = ROOT / "corpus"
    meta = {}
    for row in csv.DictReader(open(corpus / "index.csv", encoding="utf-8", newline="")):
        if row["slug"] == slug: meta = row
    raw = (corpus / f"{slug}.md").read_text(encoding="utf-8", errors="replace")
    count, _ = get_counter(allow_download=False)
    return process_paper(slug, raw, meta, count, Options(), load_taxon_table())

def cached_extraction(slug, prompt="system.txt"):
    """Cache hit only (the full runs were cached). Raises if it would need the network."""
    _, system = load_prompt(prompt)
    cfg = config_from_env(False, True, 3000)
    cfg.url = "http://127.0.0.1:9/v1"; cfg.retries = 0
    pre = pre_for(slug)
    valid = [s["n"] for s in pre.sidecar["sentences"]]
    ex = extract_paper(Client(cfg), system, pre.txt, valid, 12000, slug)
    return pre, ex
