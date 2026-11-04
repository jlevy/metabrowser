---
type: is
id: is-01m5wd9jf0zw7bwh0f8qk5eqw5
title: Untracked GitHub capability gaps from the thin-mirror Capability Map
kind: task
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-10-26T15:29:33.663Z
updated_at: 2026-11-04T17:18:23.468Z
---
The thin-mirror plan's Capability Map marks these GitHub-web capabilities as Later. Most already have a bead; these do not, so they are recorded here rather than living only in a table in a document.

Covered elsewhere, for reference: the pull-request list and Pulls tab are mb-lnkl, mb-iw1v and mb-cbak (deferred, designed in plan-2026-10-01-github-pulls-tab.md, whose spec bead mb-qftx is closed); SSH acquisition is mb-bi2c.

Not yet tracked anywhere:

- Check and status LOGS. The alpha ships the checks and statuses summary with links out to GitHub for detail; the logs themselves are not fetched or shown.
- GitHub Enterprise hosts. The reducer claims github.com and raw.githubusercontent.com only, and the size check asks github.com whatever GH_HOST names. Supporting an Enterprise host means a host allowlist, per-host credential helper wiring, and per-host canonical sources.
- Inline review-comment anchoring in the diff. Review comments are listed today with their file, line and diff hunk, and a comment's file opens at the served head at its line. Anchoring the thread INTO the diff view is not built. Note that mb-rldc covers anchored threads for the Hosted Review Format, which was removed from the stack in #246 and survives only on the do-not-merge reference branch #247, so it is not the bead for this.
- Blame, releases, and GitHub Actions views. Issues have a hosted-review bead (mb-9rrc) but no thin-mirror one.

None of these blocks the 0.12.0 release: each is an absent capability, not a defect, and nothing in the alpha claims them. File separate beads when any one is picked up; this is the inventory, not a work item.

## Notes

2026-11-04 final landing update: all 23 PRs in this delivery (21 feature PRs plus #297 and #298) are merged on main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9. Postlanding Review E: https://github.com/jlevy/metabrowser/pull/298#pullrequestreview-5772391263. Final-main CI passed all nine jobs: https://github.com/jlevy/metabrowser/actions/runs/41868009781. The verified global CLI is 0.11.1.dev1154+db52ec09; final installed-wheel, browser, coordinator manual and production-cache acceptance are complete. Current feature landing is fully accepted. Earlier pending-gate or no-merge statements are historical; preserve each original build, test and measurement provenance. This does not claim a v0.12.0 release, a quiet-host performance result or completion of separate future work.

The PR catalog/Pulls tab and existing-checkout workflows formerly listed as deferred are implemented, reviewed and merged. Retain this capability-gap inventory for check/status logs, GitHub Enterprise, inline diff-thread anchoring, blame, releases, Actions and the other unimplemented thin-mirror capabilities. Reference PR #247 remains preservation-only and does not deliver hosted-review capabilities to the product. Keep this inventory open.
