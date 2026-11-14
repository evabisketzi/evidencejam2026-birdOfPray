"""Pure-abbreviation node names over all CACHED papers, before/after paper-defined abbreviation expansion (no LLM calls).
Re-expands the cached model output twice per paper: sidecar without 'abbreviations' (= before) and with it (= after).
usage: .venv/bin/python dev/diag/abbrev_names.py [sentence|paragraph-chunks] [--head-sections] [--docs=A,B]
--head-sections: use pipeline/preprocess/sections.py from git HEAD so the model input matches the cached full run."""
import sys, csv, re, json, subprocess, importlib.util, collections
sys.path.insert(0, "dev")
from eval_murphy import *  # noqa: F401,F403  (ROOT, env defaults)
from pipeline.extract import Client, config_from_env, extract_paper, load_prompt
from pipeline.expand import expand_claims
from pipeline.main import get_preprocessor
from pipeline.preprocess.assemble import Options
from pipeline.preprocess.legend import load_taxon_table
from pipeline.preprocess.tokens import get_counter

mode = next((a for a in sys.argv[1:] if not a.startswith("--")), "sentence")
if "--head-sections" in sys.argv:
    import pipeline.preprocess.assemble as A, pipeline.preprocess.clean as CL
    src = subprocess.run(["git", "show", "HEAD:pipeline/preprocess/sections.py"], capture_output=True, text=True, check=True).stdout
    path = ROOT / ".cache" / "_sections_head.py"; path.parent.mkdir(exist_ok=True); path.write_text(src)
    spec = importlib.util.spec_from_file_location("pipeline.preprocess._sections_head", path)
    H = importlib.util.module_from_spec(spec); sys.modules[spec.name] = H; spec.loader.exec_module(H)
    A.detect_sections = H.detect_sections
    CL.heading_code, CL.is_caption, CL.is_heading = H.heading_code, H.is_caption, H.is_heading

QUAL = (r"^(?:(?:Increased|Decreased|Unchanged|Changed|Altered|Variable|Presence of|Occurrence of|Absence of|Removal of|"
        r"Introduction of|Loss of)\s+)?")
PURE = re.compile(QUAL + r"[A-Z0-9][A-Za-z0-9]*(?:[ \-/][A-Z0-9][A-Za-z0-9]*)*")


def pure(n):
    core = re.sub(QUAL, "", n)
    return bool(PURE.fullmatch(n)) and len(re.findall(r"[A-Z]", core)) >= 2


rows = list(csv.DictReader(open(ROOT / "corpus" / "index.csv", encoding="utf-8")))
DOCS = next((a.split("=", 1)[1].split(",") for a in sys.argv[1:] if a.startswith("--docs=")), None)
rows = [r for r in rows if DOCS is None or r["slug"] in DOCS]
count, _ = get_counter(allow_download=False); table = load_taxon_table(); _, system = load_prompt("system.txt")
cfg = config_from_env(False, True, 3000); cfg.url = "http://127.0.0.1:9/v1"; cfg.retries = 0
pre_fn = get_preprocessor(mode)
hits = miss = 0
before, after, changed, n_defs = [], [], [], 0
changed_by_paper = collections.Counter()
for r in rows:
    s = r["slug"]; raw = (ROOT / "corpus" / f"{s}.md").read_text(encoding="utf-8", errors="replace")
    pre = pre_fn(s, raw, r, count, Options(), table)
    try:
        ex = extract_paper(Client(cfg), system, pre.txt, [x["n"] for x in pre.sidecar["sentences"]], 12000, s,
                           pre.sidecar.get("chunk_texts"))
    except Exception:
        miss += 1
        continue
    hits += 1
    n_defs += len(pre.sidecar.get("abbreviations") or {})
    side0 = dict(pre.sidecar); side0["abbreviations"] = {}
    nb = expand_claims(s, ex.claims, side0).nodes
    na = expand_claims(s, ex.claims, pre.sidecar).nodes
    for k in nb:
        before.append(nb[k]["name"]); after.append(na[k]["name"])
        if nb[k]["name"] != na[k]["name"]:
            changed.append((s, nb[k]["name"], na[k]["name"])); changed_by_paper[s] += 1
pb = [n for n in before if pure(n)]; pa = [n for n in after if pure(n)]
out = {"mode": mode, "cache_hits": hits, "cache_misses": miss, "nodes": len(before), "definitions_found": n_defs,
       "pure_abbrev_before": len(pb), "pure_abbrev_after": len(pa), "names_changed": len(changed),
       "papers_changed": len(changed_by_paper), "remaining_pure": collections.Counter(pa).most_common(40),
       "examples": changed}
print(json.dumps(out, indent=1, ensure_ascii=False))
