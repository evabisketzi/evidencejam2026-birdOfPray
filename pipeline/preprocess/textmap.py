"""Text with a character-level map back to the raw string.

Every derived string carries ``idx``: for each character, the offset of the raw
character it came from.  Edits (deletions / replacements) rebuild the map, so a
sentence found in the cleaned text can always be located in the raw file.
"""
from __future__ import annotations

from typing import Iterable, List, Tuple

Edit = Tuple[int, int, str]  # start, end (exclusive), replacement


class Mapped:
    __slots__ = ("s", "idx")

    def __init__(self, s: str, idx: List[int]):
        assert len(s) == len(idx)
        self.s = s
        self.idx = idx

    @classmethod
    def from_raw(cls, raw: str) -> "Mapped":
        return cls(raw, list(range(len(raw))))

    def __len__(self) -> int:
        return len(self.s)

    def edit(self, edits: Iterable[Edit]) -> "Mapped":
        """Apply non-overlapping edits (overlaps are skipped, earliest wins)."""
        out: List[str] = []
        oidx: List[int] = []
        pos = 0
        n = len(self.s)
        for a, b, rep in sorted(edits, key=lambda e: (e[0], e[1])):
            if a < pos or a > n:
                continue
            b = min(b, n)
            out.append(self.s[pos:a])
            oidx.extend(self.idx[pos:a])
            if rep:
                if a < n:
                    base = self.idx[a]
                elif self.idx:
                    base = self.idx[-1] + 1
                else:
                    base = 0
                out.append(rep)
                oidx.extend([base] * len(rep))
            pos = max(pos, b)
        out.append(self.s[pos:])
        oidx.extend(self.idx[pos:])
        return Mapped("".join(out), oidx)

    def raw_span(self, a: int, b: int) -> Tuple[int, int]:
        """Raw [start, end) covering cleaned span [a, b)."""
        if not self.idx:
            return (0, 0)
        a = max(0, min(a, len(self.idx) - 1))
        b = max(a + 1, min(b, len(self.idx)))
        return (self.idx[a], self.idx[b - 1] + 1)
