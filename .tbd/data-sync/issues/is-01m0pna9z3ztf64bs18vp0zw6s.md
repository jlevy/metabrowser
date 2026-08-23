---
type: is
id: is-01m0pna9z3ztf64bs18vp0zw6s
title: Perf comparison used a live checkout, so the measurement mutated its own corpus
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m0pn7vkfkd7tfzt7r331jkp8
created_at: 2026-08-23T06:35:50.626Z
updated_at: 2026-08-23T07:24:19.384Z
---
WHAT HAPPENED. The first equivalence run compared the two builds against a working checkout. Running Metabrowser over a Python tree writes `__pycache__`, so the baseline's own run changed the tree before the candidate ran. The resulting diff was full of `.pyc` file-count deltas belonging to neither build.

WHY IT WAS EXPENSIVE. The differences were real -- the two payloads genuinely disagreed -- so nothing about the output suggested the corpus was at fault. Reading them as a behaviour change was the natural interpretation.

THE GENERAL SHAPE. Any corpus that the measurement can write to is not a corpus, it is a variable. `.pyc` is the obvious case; editor state, `.DS_Store`, index files and lock files are the same hazard.

THE FIX. Freeze the corpus before comparing: `git archive` a commit into a fresh directory and make it read-only, so a write fails loudly instead of silently changing the subject. That is what the corrected run did, and it is what produced the clean zero-difference result at depth=0. The harness should build its own frozen corpus rather than accepting a path and trusting it, or at minimum verify the tree's mtime and file count are unchanged across the two runs and refuse to report if they moved.

## Notes

FIXED in #73. devtools/compare_builds.py fingerprints the tree -- file count, directory count and newest mtime -- before the first run and after the last, and reports corpus_unchanged with both readings. A corpus that moved is visible in the result rather than showing up as a behaviour difference. Confirmed across every run in this validation: corpus_unchanged true throughout.
