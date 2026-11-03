---
type: is
id: is-01m6fesevt7mp8vz7am4456h06
title: "PR #283 A3: path-spelled remote never matches a file:// source"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m6f60pqc21gnqnct2pdq16zb
created_at: 2026-11-03T01:01:17.049Z
updated_at: 2026-11-03T01:01:17.049Z
---
Medium. Review A. src/metabrowser/cache/lender.py:224-250 and acquire.py:1019. Resolve a path remote to file:// before classifying; negative test for lookalikes.
