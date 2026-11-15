"""Build a graph for the eight reference papers from the CACHED model answers with the current code (no endpoint call).

  EVAL_PREPROCESS=paragraph-chunks python dev/cached8.py OUT.yaml [--prompt system.txt]
"""
import argparse, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dev"))
import eval_murphy                                                     # noqa: E402

DEV8 = ("YKQQZV93", "4CB9X9XE", "3KPITIV3", "6HKWT4QG", "ITXNQ843", "2F76GVEE", "4C479SU8", "V3H4MP29")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--prompt", default="system.txt")
    ap.add_argument("--skip", default="", help="comma-separated slugs to leave out (e.g. not cached yet)")
    a = ap.parse_args()
    shutil.copy(eval_murphy.graph_from_cache(a.prompt, tuple(d for d in DEV8 if d not in a.skip.split(","))), a.out)
    print(a.out)
