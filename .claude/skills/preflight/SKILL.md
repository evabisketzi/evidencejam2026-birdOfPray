---
name: preflight
description: Check that the committed pipeline works from a clean checkout exactly as the judges will run it (./run.sh corpus/ output/), with pinned deps, no committed secrets, valid CAMO output and every source document present. Use before pushing a submission, before the Sunday 6 p.m. EST snapshot, or when the user asks whether the repo is ready.
argument-hint: "[--full] [--ref BRANCH]"
---

# /preflight — is the submission ready?

1. Run the check (it builds a throwaway worktree of the commit, a fresh `.venv` from `requirements.txt`, and runs `run.sh`
   against the local mock endpoint, so no tokens and no key are needed):
   ```
   dev/preflight.sh $ARGUMENTS
   ```
   Default: 5 papers (about 2–4 min, most of it the venv install and linkml-validate). `--full`: all 308 papers (~15 min);
   run it at least once on the final submission commit. `--ref <branch>` checks a branch other than HEAD
   (for example `paragraph-chunks`).
   Run it in the background and wait for it to finish; do not poll.
2. Read the PASS / WARN / FAIL lines. For each FAIL, find the cause and propose (do not silently apply) a fix. WARNs that
   matter for judging: commits not pushed to the `team` remote, upstream not the team repo, deadline close.
3. Also confirm by hand what the script cannot:
   - the branch the team will submit is the one that gets pushed to `team` `main` (judging takes the last commit before
     Sun Nov 15, 6 p.m. EST);
   - the default `--preprocess` on that branch is the intended model;
   - `README.md` / `CLAUDE.md` describe how to run it.
4. Report: PASSED / FAILED, the commit checked, the list of problems with fixes, and what still needs a human decision.
   Never push as part of this skill; pushing needs the user's explicit go-ahead.
