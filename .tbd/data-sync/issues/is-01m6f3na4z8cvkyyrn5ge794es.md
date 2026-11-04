---
type: is
id: is-01m6f3na4z8cvkyyrn5ge794es
title: Split diff in a narrow pane hides additions as blank space
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
created_at: 2026-11-02T21:46:46.813Z
updated_at: 2026-11-04T17:14:29.509Z
started_at: 2026-11-02T21:47:04.983Z
closed_at: 2026-11-04T17:14:29.509Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Fixed in 5a4881ec on claude/v012-pr-review-workflows: Unified below 618 px, Split returns at 638 px, the stored choice is untouched. Verified in the app's own pane at 313 px, and wide panes are byte-identical. It touches plain-folder commit diffs in narrow panes only. Close when it merges.

## Notes

2026-11-03: fixed on PR 280 (5a4881ec); review C1's first-layout flash fixed at ca450430, measured in Chrome as one layout per load. CI green. Closes when the stack merges.
