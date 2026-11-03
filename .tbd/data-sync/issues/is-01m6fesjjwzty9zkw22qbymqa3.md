---
type: is
id: is-01m6fesjjwzty9zkw22qbymqa3
title: "PR #283 B1: lender own alternates and ownership checks run only with --checkout"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m6f60pqc21gnqnct2pdq16zb
created_at: 2026-11-03T01:01:20.859Z
updated_at: 2026-11-03T01:01:20.859Z
---
Medium. Review B https://github.com/jlevy/metabrowser/pull/283#pullrequestreview-5745454882. acquire.py:1050-1055, update.py _overlay_preparation. Re-apply on every open that uses a recorded lender.
