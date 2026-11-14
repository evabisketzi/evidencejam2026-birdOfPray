"""Stage 6: write YAML + JSON, validate, summarise."""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from .guard import final_integrity, validate_graph

log = logging.getLogger(__name__)
_Base = getattr(yaml, "CSafeDumper", yaml.SafeDumper)


class _NoAliasDumper(_Base):  # type: ignore[misc, valid-type]
    """Shared span objects must be written out in full, never as &anchor / *alias."""
    def ignore_aliases(self, data):
        return True


def write_yaml(graph: dict, path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        yaml.dump(graph, f, Dumper=_NoAliasDumper, allow_unicode=True, sort_keys=False, width=4096, default_flow_style=False)
    return p


def validate_yaml_file(graph: dict, path: Path, linkml: bool = True) -> Tuple[List[str], str]:
    """Re-read one YAML file and validate it (JSON Schema + whole-graph checks, and linkml-validate when installed)."""
    errors: List[str] = []
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        exc = validate_graph(data)
        if exc is not None:
            errors.append(f"{Path(path).name}: JSON Schema: {exc.name}: {exc.message[:160]}")
    except Exception as e:  # noqa: BLE001
        errors.append(f"{Path(path).name}: cannot be read back ({type(e).__name__}: {str(e)[:100]})")
    errors += final_integrity(graph)[:20]
    ran = "JSON Schema"
    if linkml and linkml_exe():
        errors += _linkml(Path(path))
        ran += " + linkml-validate"
    else:
        ran += " (linkml-validate not installed here, so it was not run)"
    return errors, ran


def write_outputs(graph: dict, out_dir) -> Tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    yp, jp = out / "camo_graph.yaml", out / "camo_graph.json"
    write_yaml(graph, yp)
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=1)
    return yp, jp


def linkml_exe() -> Optional[str]:
    """linkml-validate on PATH, or beside the running interpreter (a venv's bin/ is usually not on PATH)."""
    import sys
    exe = shutil.which("linkml-validate")
    if exe:
        return exe
    cand = Path(sys.executable).parent / "linkml-validate"
    return str(cand) if cand.exists() else None


def _linkml(path: Path) -> List[str]:
    exe = linkml_exe()
    if not exe:
        return []
    schema = Path(__file__).resolve().parent.parent / "schema" / "causalmosaic.yaml"
    r = subprocess.run([exe, "-s", str(schema), "-C", "CausalGraph", str(path)], capture_output=True, text=True, timeout=3600)
    errs = [ln for ln in (r.stdout + r.stderr).splitlines() if "[ERROR]" in ln]
    if r.returncode != 0 and not errs:
        errs = [f"linkml-validate exited with {r.returncode}: {(r.stderr or r.stdout)[-200:]}"]
    return [f"{path.name}: {e}" for e in errs[:20]]


def validate_outputs(graph: dict, yaml_path: Path, json_path: Path, linkml: bool = True) -> Tuple[List[str], str]:
    """Errors (empty = fine) and a note on which validators ran.  Both files are re-read from disk and checked."""
    errors: List[str] = []
    for label, loader, p in (("json", lambda f: json.load(f), json_path), ("yaml", lambda f: yaml.safe_load(f), yaml_path)):
        try:
            with open(p, encoding="utf-8") as f:
                data = loader(f)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{p.name}: cannot be read back ({type(e).__name__}: {str(e)[:100]})")
            continue
        exc = validate_graph(data)
        if exc is not None:
            errors.append(f"{p.name}: JSON Schema: {exc.name}: {exc.message[:160]}")
    errors += final_integrity(graph)[:20]
    ran = "JSON Schema"
    if linkml and linkml_exe():
        errors += _linkml(json_path) + _linkml(yaml_path)
        ran += " + linkml-validate"
    else:
        ran += " (linkml-validate not installed here, so it was not run)"
    return errors, ran


def summary(graph: dict, outcomes: List[dict], seconds: float, validators: str, doi_counts: Optional[Dict[str, int]] = None) -> str:
    docs = len(graph["source_documents"])
    done = [o for o in outcomes if not o.get("error")]
    failed = [o for o in outcomes if o.get("error")]
    nulls = sum(1 for e in graph["edges"] if e.get("negated"))
    pt = sum(o.get("prompt_tokens", 0) for o in outcomes)
    ct = sum(o.get("completion_tokens", 0) for o in outcomes)
    n = max(1, len(outcomes))
    lines = [
        f"papers: {len(done)} processed, {len(failed)} failed (of {len(outcomes)} attempted; {docs} documents in source_documents)",
        *( [f"DOIs: {doi_counts['index']} from index.csv, {doi_counts['markdown']} recovered from the markdown, {doi_counts['none']} none"] if doi_counts else [] ),
        f"graph: {len(graph['edges'])} edges, {len(graph['nodes'])} nodes, {nulls} null results",
        f"tokens: prompt {pt:,} + completion {ct:,} = {pt + ct:,}; per paper {pt / n:,.0f} + {ct / n:,.0f}",
        f"validation: {validators}",
        f"wall clock: {seconds:,.1f} s",
    ]
    for o in failed[:10]:
        lines.append(f"  failed {o['doc']}: {o['error'][:150]}")
    if len(failed) > 10:
        lines.append(f"  ... and {len(failed) - 10} more (see run_log.json)")
    return "\n".join(lines)
