"""Re-expand the CACHED full-baseline model output for all 308 papers with the current code and count template artefacts in node names."""
import sys, csv, re, json; sys.path.insert(0, "dev")
from eval_murphy import *
from pipeline.extract import Client, config_from_env, extract_paper, load_prompt
from pipeline.expand import expand_claims
from pipeline.main import get_preprocessor
from pipeline.preprocess.assemble import Options
from pipeline.preprocess.legend import load_taxon_table
from pipeline.preprocess.tokens import get_counter
rows = list(csv.DictReader(open(ROOT / "corpus/index.csv", encoding="utf-8")))
count, _ = get_counter(allow_download=False); table = load_taxon_table(); _, system = load_prompt("system.txt")
cfg = config_from_env(False, True, 3000); cfg.url = "http://127.0.0.1:9/v1"; cfg.retries = 0
names = []
for r in rows:
    s = r["slug"]; raw = (ROOT / f"corpus/{s}.md").read_text(encoding="utf-8", errors="replace")
    pre = get_preprocessor("sentence")(s, raw, r, count, Options(), table)
    try:
        ex = extract_paper(Client(cfg), system, pre.txt, [x["n"] for x in pre.sidecar["sentences"]], 12000, s)
    except Exception:
        continue
    names += [n["name"] for n in expand_claims(s, ex.claims, pre.sidecar).nodes.values()]
pats = {"action named as presence/occurrence": r"^(Presence|Occurrence) of (establishment|planting|release|removal|introduction|restoration|harvest|reintroduction|construction|application)",
        "adjective in property slot": r"^[A-Z][a-z]+( or [a-z]+)? of [a-z ]+ (type|use|class|status)$",
        "double action (Removal of ... closure/removal)": r"^Removal of .*(closure|removal|cessation)",
        "taxon repeated (X of Y of Y)": r" of ([A-Z][a-z]+ [a-z]+) of \1$",
        "adjective as thing (... of herbaceous)": r" of (herbaceous|woody|native|exotic|natural|aquatic|terrestrial|total)$"}
print(len(names), "node names re-expanded")
for k, p in pats.items():
    m = [n for n in names if re.search(p, n)]
    print(f"{len(m):5}  {k}  {m[:3]}")
