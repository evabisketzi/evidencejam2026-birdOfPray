"""Step 10 (optional, off by default): drop numbered sentences with no causal/comparison/negation/hedge
wording and no legend species; keep the sentence before an anaphoric opener ("This", "However", ...)."""
from __future__ import annotations

import re
from typing import List, Sequence

CAUSAL = re.compile(
    r"\b(?:increas\w*|decreas\w*|reduc\w*|suppress\w*|affect\w*|effects?|higher|lower|greater|fewer|more|less|differ\w*|"
    r"promot\w*|inhibit\w*|kill\w*|limit\w*|enhanc\w*|facilitat\w*|prevent\w*|depend\w*|respon[ds]\w*|result\w*)\b", re.I)
NEG_HEDGE = re.compile(
    r"\b(?:not|no|neither|nor|may|might|could|suggest\w*|appear\w*|likely|possibl\w*|indicat\w*)\b|n['’]t\b", re.I)
OPENER = re.compile(r"^\s*(?:This|These|It|Such|However|Thus)\b")


def apply_filter(texts: Sequence[str], forms: Sequence[str]) -> List[bool]:
    """Return keep-flags aligned with `texts`."""
    base = []
    for t in texts:
        has_species = any(f in t for f in forms if len(f) >= 4)
        base.append(bool(CAUSAL.search(t) or NEG_HEDGE.search(t) or has_species))
    keep = list(base)
    for i, t in enumerate(texts):
        if base[i] and i > 0 and OPENER.match(t):
            keep[i - 1] = True
    return keep
