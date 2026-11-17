---
type: is
id: is-01m7kpnfbtzejh3redbeppejmp
title: "CI speed 3.2: path classes, so a documentation-only or macOS-only pull request runs lint, distribution, and the unit and golden jobs once (only if the owner wants them)"
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
created_at: 2026-11-17T02:51:34.649Z
updated_at: 2026-11-17T02:51:34.649Z
---
Phase 3 of plan-2026-11-16-fast-ci.md, Path Classes; needs the owner's answer to Q7. The plan job classes a pull request as light when every changed path is under docs/, apps/macos/, or .tbd/, or is a Markdown file at the repository root; main never uses classes. Of the last 150 merged pull requests, 13 changed only documentation and 11 only apps/macos and documentation. The classifier lives in devtools/ci_plan.sh with tests over path lists, ci-ok accepts the skipped jobs only for a light run, and devtools/check_ci.py holds main to the full set.
