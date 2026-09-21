---
type: is
id: is-01m30x2tyka6xd3ta5ahbwr952
title: Pre-commit biome reformats files make lint-check does not own
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-21T02:35:22.450Z
updated_at: 2026-09-21T07:17:25.486Z
closed_at: 2026-09-21T07:17:25.485Z
close_reason: Merged to main as 4d84c019 (PR 222). biome.json now names the same roots devtools/lint.py checks, so the pre-commit hook and the gate agree on what biome owns; verified in place that biome ci still checks 215 files and passes while a conformance corpus is no longer claimed.
resolution: null
duplicate_of: null
---
lefthook.yml's biome command globs *.{js,css,json} with no path restriction and biome.json includes ** , so staging any JSON runs biome --write over it. devtools/lint.py BIOME_PATHS only covers devtools/artifact-contract-browser-check.mjs, src/metabrowser/static, src/metabrowser/builtin_plugins, tests/dom, explorations and the root config files. So the hook rewrites files no gate checks: the hosted-review conformance corpora (a 7-line change became 640 changed lines in one observed case, fighting the committed one-line-per-case style and guaranteeing cross-layer conflicts), tests/fixtures JSON, and package-lock.json. Fix: make biome.json includes name the same roots BIOME_PATHS lists, so the hook and the gate agree on what biome owns; verify biome ci still passes on those paths and that staging a corpus file becomes a no-op. Found while fixing mb-vs5q, where the implementer had to commit with --no-verify to avoid the churn.
