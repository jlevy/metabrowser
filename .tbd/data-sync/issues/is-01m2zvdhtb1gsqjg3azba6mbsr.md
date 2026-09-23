---
type: is
id: is-01m2zvdhtb1gsqjg3azba6mbsr
title: Optional cleanup of local PR-sizing shortcut copies
kind: task
status: open
priority: 4
version: 6
spec_path: null
delegate: null
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-20T16:47:01.961Z
updated_at: 2026-09-23T01:32:14.324Z
started_at: 2026-09-23T00:38:14.508Z
---
Independent process-document maintenance for PR #219. Keep the local shortcut guidance while useful and remove duplicate copies opportunistically when the available upstream text is equivalent. Do not wait for a tbd release, block #219 on an upstream publication, or make this cleanup a dependency of Metabrowser feature work, testing, stack landing, or release.

## Notes

2026-09-22 user clarification: nothing is held on tbd. This is optional process-document cleanup only. A tbd release is not a prerequisite for reviewing or landing #219, and neither #219 nor this bead gates Metabrowser feature work, testing, stack landing, or releases. Keep the existing local guidance as needed; remove duplicate copies opportunistically after comparing available upstream text. The earlier recommendation to hold #219 for a release is superseded.

Historical audit:
2026-09-22 status audit: keep this follow-up and Metabrowser #219 open. Upstream https://github.com/jlevy/tbd/pull/316 merged 2026-09-20 (a92ecab959b726a471c45ed4a834bfdbaa88c8b6), but latest published get-tbd v0.9.0 is dated 2026-09-16: https://github.com/jlevy/tbd/releases/tag/v0.9.0 . Released shortcuts still lack the consolidation/stack-size guidance in the fork. After a release includes #316, compare the shipped resources and remove the local fork. #219 has no substantive review; its current lint failure is the frozen AnyIO 4.14.1 vulnerability audit, corrected on current main. Refresh against current main and rerun checks if pursuing the PR. This is process maintenance outside the v0.12 product stack; remove the stale release:v0.11.0 label without assigning it to v0.12.
