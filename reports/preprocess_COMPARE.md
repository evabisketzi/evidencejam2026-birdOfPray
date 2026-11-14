# Preprocessing comparison (20261114_105939); mean (min–max) over repeats

**sentence filter (ours):** split into sentences, drop cited-background sentences, compress statistics. **paragraph selection (teammate):** clean paragraphs, drop introduction/methods, keep paragraphs by cue score, then split into sentences. Same prompt, SPECIES and CONTEXT in both; two gold papers, cache off.

| metric | paragraph selection (teammate) (n=3) | sentence filter (ours) (n=3) |
|---|---:|---:|
| micro standard F1 | 0.351 (0.316–0.377) | 0.321 (0.312–0.328) |
| micro strict F1 | 0.279 (0.228–0.328) | 0.282 (0.280–0.285) |
| micro loose F1 | 0.524 (0.509–0.541) | 0.488 (0.430–0.522) |
| standard precision | 0.348 (0.333–0.371) | 0.306 (0.300–0.309) |
| standard recall | 0.356 (0.300–0.383) | 0.339 (0.325–0.350) |
| null recall | 0.181 (0.000–0.292) | 0.333 (0.292–0.375) |
| predicted edges | 123 (108–136) | 133 (130–136) |
| prompt tokens (2 papers) | 11,851 (11,409–12,727) | 11,982 (11,880–12,060) |
| completion tokens (2 papers) | 2,939 (2,675–3,238) | 3,070 (2,927–3,198) |
| seconds (sum) | 735 (620–877) | 500 (391–600) |
| loose F1 4CB9X9XE | 0.152 (0.135–0.178) | 0.042 (0.038–0.050) |
| loose F1 murphy2005 | 0.809 (0.772–0.843) | 0.823 (0.770–0.855) |
| std F1 4CB9X9XE | 0.108 (0.090–0.139) | 0.024 (0.019–0.033) |
| std F1 murphy2005 | 0.536 (0.457–0.586) | 0.548 (0.524–0.593) |
