---
type: is
id: is-01m7ey9r1ecpxkvdrdez7ax3r7
title: "Diff help text: --format lists yaml, --diff omits A...B"
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7ey9fq9v53mp3c974mg2d89
created_at: 2026-11-15T06:28:46.765Z
updated_at: 2026-11-15T06:28:46.765Z
---
The --format help lists yaml for diff, but diff_cli.run_diff refuses it; diff_cli supports A...B ranges that the --diff help does not mention.
