---
type: is
id: is-01m2zvdhtb1gsqjg3azba6mbsr
title: "Unfork docs/tbd PR-sizing shortcuts (PR #219) once get-tbd ships tbd #316"
kind: task
status: open
priority: 3
version: 4
spec_path: null
delegate: null
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-20T16:47:01.961Z
updated_at: 2026-09-23T00:39:04.397Z
started_at: 2026-09-23T00:38:14.508Z
---
Metabrowser PR #219 (branch docs/pr-sizing-guidance, OPEN as of 2026-09-20) carries forked local copies of the tbd PR-sizing shortcuts. Upstream jlevy/tbd PR #316 is MERGED (2026-09-20T06:17:47Z), so once a get-tbd release ships it, drop the fork and consume the released shortcuts.

## Notes

2026-09-22 status audit: keep this follow-up and Metabrowser #219 open. Upstream https://github.com/jlevy/tbd/pull/316 merged 2026-09-20 (a92ecab959b726a471c45ed4a834bfdbaa88c8b6), but latest published get-tbd v0.9.0 is dated 2026-09-16: https://github.com/jlevy/tbd/releases/tag/v0.9.0 . Released shortcuts still lack the consolidation/stack-size guidance in the fork. After a release includes #316, compare the shipped resources and remove the local fork. #219 has no substantive review; its current lint failure is the frozen AnyIO 4.14.1 vulnerability audit, corrected on current main. Refresh against current main and rerun checks if pursuing the PR. This is process maintenance outside the v0.12 product stack; remove the stale release:v0.11.0 label without assigning it to v0.12.
