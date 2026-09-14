---
type: is
id: is-01m2ehe9c902bfmb9gnfq3e32z
title: Gate releases on time to first directory tree rows for a repository-shaped corpus
kind: task
status: in_progress
priority: 0
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels:
  - performance
  - first-paint
  - release
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-09-13T23:25:34.984Z
updated_at: 2026-09-14T01:29:40.662Z
---
Make time to first directory tree rows a standard, gated release metric on a repository-shaped corpus.

Why: the first paint of the directory tree must be rapid, and the release comparison did not measure it on a tree where it is slow. exp-032 used the synthetic build_corpus, so a 10-34 s first-rows delay on a real repository shipped in every release since v0.1.0 (see the P0 bug for the prewalk).

Scope:
1. Deterministic contract in make verify (no wall clock): on a tree with many directories and nested .gitignore files, root rows are readable from the inventory before any directory below the root is traversed, and producing them reads no nested .gitignore outside the root's ancestor chain.
2. Release comparison: add the project-shaped corpus (bench_serving --corpus project; nested .gitignore, many directories, ignored virtualenvs) to the release procedure, and record backend spawn-to-first-root-row and browser first_row_ms from a cold start.
3. Hard budget, set from a quiet-machine measurement and recorded beside the constant (AGENTS.md: measure before bounding), for first root rows on that corpus; a candidate that exceeds it is rejected like any responsiveness gate.
4. Document the metric in explorations/performance-loop/README.md release steps and link it from the release checklist.

## Notes

Done on claude/fast-first-tree-paint (commit 2e9e2066):
1. Deterministic contract in make verify: tests/test_gitignore_hierarchical.py asserts root rows are readable while a deeper directory's scan is held open, that building the gitignore matcher traverses nothing, and that a verdict reads only its ancestor chain. The first two fail on the old pre-walk design.
4. Documented: explorations/performance-loop/README.md "Comparing a candidate with the previous release" now requires the project-10 corpus and first-rows reporting (backend first_row from compare_builds, browser first_row_ms) for both conditions.

Remaining (quiet machine, with mb-afdb):
2. Run the release comparison on project-10 cold and record backend first_row and browser first_row_ms for control and candidate.
3. From that measurement, promote first_row_ms (currently policy "target", maximum 500) to a hard gate at a measured value, and consider making compare refuse release labels whose corpus_shape is not the repository-shaped corpus.

Reference numbers from a loaded machine (not budget evidence): on a 146,677-file repository, first root rows after launch were 0.70-1.64 s on the fixed build vs 3.7-13.2 s on main; a cold real-browser load painted the tree 245 ms after navigation vs about 9.5 s.
