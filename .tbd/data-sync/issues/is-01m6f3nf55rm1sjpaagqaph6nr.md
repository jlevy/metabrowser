---
type: is
id: is-01m6f3nf55rm1sjpaagqaph6nr
title: Hold every v0.12 surface to the design system
kind: task
status: closed
priority: 1
version: 17
delegate: claude-code@spud10
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m6f3njzx91ssw9yq9x2smtv5
  - type: blocks
    target: is-01m6f3nj5vpvkbw0m300dcy3jr
  - type: blocks
    target: is-01m6f3nmnmmceb1c0rgwvdg8as
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
child_order_hints:
  - is-01m6f3nfjp6kwy4m46fjjdpfbb
  - is-01m6f3ng0aqr0eq1pbpp5nzf7e
  - is-01m6f3ngds6yf76vnh9qwfzm5k
  - is-01m6f3ngtspxj6q61n1dmv9672
  - is-01m6f3nh8edcavm9h8kfgav2ne
  - is-01m6f3nhp61he288qpjtst9jb1
hold: null
hold_until: null
created_at: 2026-11-02T21:46:51.940Z
updated_at: 2026-11-04T17:18:12.572Z
started_at: 2026-11-02T21:47:06.817Z
closed_at: 2026-11-04T17:14:30.866Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Running on the branch. Audit of everything added since v0.11.0, with a finding list surface by surface.

## Notes

2026-11-03: done on PR 280: design-system pass and nine checks; the owner's sans rule for messages at 996ea90d (mb-nts1, test_serif_is_only_for_documents). Merged forward to 284 and 283. Closes when the stack merges.


2026-11-03 pause: a follow-up review of 996ea90d (the sans rule) on PR 280 was started and stopped before it verified anything, so it is still owed: check test_serif_is_only_for_documents, both reading fonts and the system font set in Chrome, and any other message surface still in serif.

2026-11-03 independent-review integration at final tip 58270d69. Owed sans-rule follow-up is completed: Review D at 996ea90d found actual system-font measurement mismatch;64fa6b1f fixes it, Review E independently rechecks clean, and nine remote CI jobs are green. Eight Chrome font/theme cases preserve ordinary document width and use the actual system message measure. Keep this bead open per its owner instruction: closes when the stack merges. Final full verification, publication and remote CI are coordinator gates still pending; no PR merged.

2026-11-04 final landing update: all 23 PRs in this delivery (21 feature PRs plus #297 and #298) are merged on main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9. Postlanding Review E: https://github.com/jlevy/metabrowser/pull/298#pullrequestreview-5772391263. Final-main CI passed all nine jobs: https://github.com/jlevy/metabrowser/actions/runs/41868009781. The verified global CLI is 0.11.1.dev1154+db52ec09; final installed-wheel, browser, coordinator manual and production-cache acceptance are complete. Current feature landing is fully accepted. Earlier pending-gate or no-merge statements are historical; preserve each original build, test and measurement provenance. This does not claim a v0.12.0 release, a quiet-host performance result or completion of separate future work.

The owed sans-font follow-up review was completed and its measured system-font mismatch fixed; PR #280 and later design layers are merged. Final-main font/jump acceptance is recorded in the coordinator receipt. The previous owner-merge condition is satisfied. Preserve the dated review and font evidence.
