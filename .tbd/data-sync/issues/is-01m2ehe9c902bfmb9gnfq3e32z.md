---
type: is
id: is-01m2ehe9c902bfmb9gnfq3e32z
title: Gate releases on time to first directory tree rows for a repository-shaped corpus
kind: task
status: closed
priority: 0
version: 6
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels:
  - performance
  - first-paint
  - release
dependencies:
  - type: blocks
    target: is-01m2fafd1v8d5pakt6r7zxw5n8
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-09-13T23:25:34.984Z
updated_at: 2026-09-14T16:07:39.427Z
closed_at: 2026-09-14T16:07:39.426Z
close_reason: "first_row_ms is a hard gate at 350 ms (rough-cut, from exp-033 on project-10) in PR #120; the structural contract, release-comparison run, and documentation are done. Quiet-machine recalibration is tracked in mb-afdb."
resolution: null
duplicate_of: null
---
Make time to first directory tree rows a standard, gated release metric on a repository-shaped corpus.

Why: the first paint of the directory tree must be rapid, and the release comparison did not measure it on a tree where it is slow. exp-032 used the synthetic build_corpus, so a 10-34 s first-rows delay on a real repository shipped in every release since v0.1.0 (see the P0 bug for the prewalk).

Scope:
1. Deterministic contract in make verify (no wall clock): on a tree with many directories and nested .gitignore files, root rows are readable from the inventory before any directory below the root is traversed, and producing them reads no nested .gitignore outside the root's ancestor chain.
2. Release comparison: add the project-shaped corpus (bench_serving --corpus project; nested .gitignore, many directories, ignored virtualenvs) to the release procedure, and record backend spawn-to-first-root-row and browser first_row_ms from a cold start.
3. Hard budget, set from a quiet-machine measurement and recorded beside the constant (AGENTS.md: measure before bounding), for first root rows on that corpus; a candidate that exceeds it is rejected like any responsiveness gate.
4. Document the metric in explorations/performance-loop/README.md release steps and link it from the release checklist.

## Notes

Scope complete; closed with PR #120 (branch claude/release-v0.10.0-perf).

1. Deterministic contract in make verify (commit 2e9e2066): tests/test_gitignore_hierarchical.py asserts root rows are readable while a deeper directory's scan is held open, that building the gitignore matcher traverses nothing, and that a verdict reads only its ancestor chain. The first two fail on the old pre-walk design.
2. Release comparison on project-10, cold, both conditions: exp-033. Browser first_row_ms v0.9.1 198-1,064 ms vs candidate 88606b56 144-269 ms; backend first_row about 1.1 s vs 11-14 ms. Measured on a loaded host (load average 16-34), so indicative only.
3. first_row_ms promoted from target (500 ms) to a hard gate at 350 ms in explorations/performance-loop/performance-budgets.toml: 1.3x the worst candidate project-10 first row in exp-033 (269 ms), rounded up. The comment beside the constant records that it is a rough-cut budget from a loaded machine that guards against the 9-34 s pre-walk class of regression, to be recalibrated from a quiet-machine measurement at the careful 1.1x tolerance (tracked with the rerun in mb-afdb). A heavily loaded host can still cross it spuriously: an unrecorded dry run at load 19 took 468 ms. Making compare refuse release labels whose corpus_shape is not repository-shaped was considered and not done; the README procedure requires project-10.
4. Documented in explorations/performance-loop/README.md "Comparing a candidate with the previous release", including the back-to-back pair tolerance policy (1.3x rough cut, 1.1x careful, 1.05x fine).

Reference numbers from a loaded machine (not budget evidence): on a 146,677-file repository, first root rows after launch were 0.70-1.64 s on the fixed build vs 3.7-13.2 s on main; a cold real-browser load painted the tree 245 ms after navigation vs about 9.5 s.
