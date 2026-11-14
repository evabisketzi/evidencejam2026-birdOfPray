"""python -m pipeline.validate OUTPUT_DIR   -> JSON Schema + whole-graph checks + linkml-validate (when available) on both files.
Writes OUTPUT_DIR/validation.json and exits non-zero on any problem."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import List, Optional

from .write import linkml_exe, validate_outputs


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: python -m pipeline.validate OUTPUT_DIR", file=sys.stderr)
        return 2
    d = Path(args[0])
    yp, jp = d / "camo_graph.yaml", d / "camo_graph.json"
    t0 = time.time()
    if not (yp.exists() and jp.exists()):
        res = {"ok": False, "yaml_ok": False, "json_ok": False, "validators": "none", "errors": ["camo_graph.yaml/.json missing"], "seconds": 0}
    else:
        with open(jp, encoding="utf-8") as f:
            graph = json.load(f)
        errors, ran = validate_outputs(graph, yp, jp)
        res = {"ok": not errors, "yaml_ok": not any(e.startswith("camo_graph.yaml") for e in errors),
               "json_ok": not any(e.startswith("camo_graph.json") for e in errors),
               "validators": ran, "linkml_validate": bool(linkml_exe()), "errors": errors[:50], "seconds": round(time.time() - t0, 1)}
    (d / "validation.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(f"validation: {'OK' if res['ok'] else 'FAILED'}  yaml_ok={res['yaml_ok']} json_ok={res['json_ok']}  ({res['validators']}, {res['seconds']}s)")
    for e in res["errors"][:10]:
        print("  " + e, file=sys.stderr)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
