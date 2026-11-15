"""Rebuild a graph from the SAVED model answers of an earlier run with the CURRENT stages 1, 4, 5, 6 (no endpoint call).

  python dev/replay.py dev/jobs/out/JOB OUT.yaml [--docs A,B] [--preprocess X] [--set dev8] [--ontology off|lookup[:entities]]

Stage 5b (ontology lookup) is applied as the run had it (run_log.json "ontology"; runs from before the stage: off), or as
--ontology says.  A run made with select replays as lookup: the selection answers are not in raw_responses.jsonl.

JOB must hold raw_responses.jsonl (runs since 2026-11-14 22:30) and run_log.json (for the prompt and preprocessing).  Each
paper's answers are handed back in call order (chunks, then the repair call if there was one).  Exact and noise-free, so
it is the before/after check for parse/expand/guard/write changes on several distinct response sets.  A paper whose
preprocessing now yields a different number of chunks is replayed as far as the answers go and reported.
"""
import argparse, csv, json, logging, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
for k, v in (("BRINE_URL", "http://127.0.0.1:9/v1"), ("BRINE_MODEL", "replay"), ("BRINE_API_KEY", "unused")):
    os.environ.setdefault(k, v)

from pipeline.extract import Result, load_prompt                       # noqa: E402

DEV8 = "YKQQZV93,4CB9X9XE,3KPITIV3,6HKWT4QG,ITXNQ843,2F76GVEE,4C479SU8,V3H4MP29"


class ReplayClient:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = 0
        self.short = False

    def complete(self, system, user, label=""):
        self.calls += 1
        if not self.answers:
            self.short = True
            return Result("", 0, 0, 0.0, True)
        return Result(self.answers.pop(0), 0, 0, 0.0, True)


def replay(job: Path, out: Path, docs=None, preprocess=None, prompt=None, ontology=None):
    from pipeline.main import get_preprocessor, read_index
    from pipeline.ontology_stage import OntologyStage, regrounded
    from pipeline.extract import extract_paper
    from pipeline.expand import expand_claims
    from pipeline.guard import guard_paper, merge
    from pipeline.preprocess.assemble import Options
    from pipeline.preprocess.legend import load_taxon_table
    from pipeline.preprocess.tokens import get_counter
    from pipeline.write import write_yaml
    rl = json.load(open(job / "run_log.json"))
    raw = {}
    for line in open(job / "raw_responses.jsonl", encoding="utf-8"):
        d = json.loads(line)
        raw[d["doc"]] = d["responses"]
    pre_name = preprocess or rl.get("preprocess", "paragraph-chunks")
    _, system = load_prompt(prompt or rl.get("prompt", "system.txt"))
    opts = Options(cite_filter=rl.get("cite_filter", "strict"), taxon_groups=bool(rl.get("taxon_groups")),
                   keep_results=bool(rl.get("keep_results")), clean_variants=bool(rl.get("clean_variants")),
                   chunk_tokens=int(rl.get("chunk_tokens") or 0))
    index = read_index(ROOT / "corpus")
    rows = {r["slug"]: r for r in index}
    want = [d for d in (docs or raw) if d in raw]
    count, _ = get_counter(allow_download=False)
    table = load_taxon_table()
    pre_fn = get_preprocessor(pre_name)
    per, notes = {}, []
    if ontology:
        o_mode, _, o_fields = ontology.partition(":")
    else:
        o_mode, o_fields = rl.get("ontology", "off"), rl.get("ontology_fields", "all")
    if o_mode == "select":
        notes.append("run used --ontology select: replayed as lookup (selection answers are not saved)")
        o_mode = "lookup"
    if o_mode not in ("off", "lookup"):
        raise SystemExit(f"--ontology: off or lookup[:all|:entities], not {ontology!r}")
    onto = OntologyStage("lookup", o_fields or "all") if o_mode == "lookup" else None
    for slug in want:
        text = (ROOT / "corpus" / f"{slug}.md").read_text(encoding="utf-8", errors="replace")
        pre = pre_fn(slug, text, rows[slug], count, opts, table)
        valid = [s["n"] for s in pre.sidecar["sentences"]]
        cl = ReplayClient(raw[slug])
        ex = extract_paper(cl, system, pre.txt, valid, 12000, slug, pre.sidecar.get("chunk_texts"))
        if cl.short or cl.answers:
            notes.append(f"{slug}: {len(raw[slug])} saved answers, {cl.calls} calls now")
        exp = expand_claims(slug, ex.claims, pre.sidecar)
        nodes, edges, _ = guard_paper(slug, exp.nodes, exp.edges)
        if onto is not None:
            nodes, edges, _, _, _ = regrounded(nodes, edges, slug, onto, guard_paper)
        per[slug] = (nodes, edges)
    g = merge([rows[s] for s in want], per)
    write_yaml(g, out)
    return out, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job")
    ap.add_argument("out")
    ap.add_argument("--docs")
    ap.add_argument("--set", choices=("dev8",))
    ap.add_argument("--preprocess")
    ap.add_argument("--prompt")
    ap.add_argument("--ontology", help="off | lookup | lookup:entities (default: as the replayed run had it)")
    a = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)
    docs = (a.docs or (DEV8 if a.set == "dev8" else "")).split(",") if (a.docs or a.set) else None
    out, notes = replay(Path(a.job), Path(a.out), docs, a.preprocess, a.prompt, a.ontology)
    for n in notes:
        print("note:", n)
    print(out)


if __name__ == "__main__":
    main()
