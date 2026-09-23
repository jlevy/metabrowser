---
type: is
id: is-01m2zpx1svn4c8an4mm9r9mv8z
title: "S216-13: PR 216 Lows: 16 MiB classify-before-read, batch deadline scaling, symlink normalization, rollup names, CHANGELOG, QA runbook, spec box"
kind: bug
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - stack:pr216
  - release:v0.12.0
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:28:06.966Z
updated_at: 2026-09-23T05:32:22.281Z
closed_at: 2026-09-23T05:32:22.280Z
close_reason: "Done. Classify-before-read is fixed on codex/v012-foundation-stabilization (PR #226) (7c380cca) and symlink component resolution in f7d251f2, bounded at PATH_MAX in 899ff0e2. Already fixed earlier on the stack: batch deadline scaling 90aeda88, rollup names 60dfeaeb, SDK source kind 6f503835, CHANGELOG and QA runbook ad96356f. The spec's 1B-c edge-case box was already checked."
resolution: null
duplicate_of: null
---
Finding S216-13 from the v0.11 stabilization review. Owning layer: PR #216. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S216-13.
