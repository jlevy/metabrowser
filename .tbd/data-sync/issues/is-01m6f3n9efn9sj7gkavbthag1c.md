---
type: is
id: is-01m6f3n9efn9sj7gkavbthag1c
title: Back from a file loses the reader's place in a long pull request
kind: bug
status: closed
priority: 1
version: 4
delegate: claude-code@spud10
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-02T21:46:46.094Z
updated_at: 2026-11-04T17:14:29.900Z
started_at: 2026-11-02T21:47:04.603Z
closed_at: 2026-11-04T17:14:29.900Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Fixed in 7d5339ff on claude/v012-pr-review-workflows: history.state.pullPlace keeps block and offset. Measured in Chrome with the back/forward cache off on 34-file, 137-file, and 120-text pages. Not verified outside Chrome; Safari lacks scroll anchoring. Close when it merges.

## Notes

2026-11-03: fixed on PR 280 (7d5339ff); review findings A4, C3, and C5 on it fixed at 454a509e. CI green at 996ea90d. Closes when the stack merges.
