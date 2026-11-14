---
type: is
id: is-01m5wd9jf0zw7bwh0f8qk5eqw5
title: Untracked GitHub capability gaps from the thin-mirror Capability Map
kind: task
status: open
priority: 3
version: 4
spec_path: docs/project/specs/done/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-10-26T15:29:33.663Z
updated_at: 2026-11-14T18:50:07.094Z
---
The thin-mirror plan's Capability Map marks these GitHub-web capabilities as Later. They have no bead of their own, so they are recorded here rather than only in a table in a document.

Tracked elsewhere: the pull-request list and Pulls tab shipped in 0.12.0 (mb-lnkl, mb-iw1v, mb-cbak, closed); SSH acquisition is mb-bi2c (deferred).

Not yet tracked anywhere:

- Check and status logs. 0.12.0 has a Checks tab with the checks and statuses summary and links out to GitHub; the logs themselves are not fetched or shown.
- GitHub Enterprise hosts. The reducer claims github.com and raw.githubusercontent.com only, and the size check asks github.com whatever GH_HOST names. Supporting an Enterprise host means a host allowlist, per-host credential helper wiring, and per-host canonical sources.
- Inline review-comment anchoring in the diff. Review comments are listed with their file, line and diff hunk, and a comment's file opens at its line; anchoring the thread in the diff view is not built, and the Pulls tab plan lists it as a non-goal. mb-rldc covers anchored threads for the removed Hosted Review Format, which survives only on the do-not-merge reference branch (#247), so it is not the bead for this.
- Blame, releases, and GitHub Actions views. Issues have a hosted-review bead (mb-9rrc, deferred) but no thin-mirror one.

None of these is a defect. File a separate bead when one is picked up; this is the inventory, not a work item.

## Notes

2026-11-04 final landing update: all 23 PRs in this delivery (21 feature PRs plus #297 and #298) are merged on main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9. Postlanding Review E: https://github.com/jlevy/metabrowser/pull/298#pullrequestreview-5772391263. Final-main CI passed all nine jobs: https://github.com/jlevy/metabrowser/actions/runs/41868009781. The verified global CLI is 0.11.1.dev1154+db52ec09; final installed-wheel, browser, coordinator manual and production-cache acceptance are complete. Current feature landing is fully accepted. Earlier pending-gate or no-merge statements are historical; preserve each original build, test and measurement provenance. This does not claim a v0.12.0 release, a quiet-host performance result or completion of separate future work.

The PR catalog/Pulls tab and existing-checkout workflows formerly listed as deferred are implemented, reviewed and merged. Retain this capability-gap inventory for check/status logs, GitHub Enterprise, inline diff-thread anchoring, blame, releases, Actions and the other unimplemented thin-mirror capabilities. Reference PR #247 remains preservation-only and does not deliver hosted-review capabilities to the product. Keep this inventory open.
