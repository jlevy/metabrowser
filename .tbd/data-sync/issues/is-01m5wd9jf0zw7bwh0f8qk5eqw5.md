---
type: is
id: is-01m5wd9jf0zw7bwh0f8qk5eqw5
title: Untracked GitHub capability gaps from the thin-mirror Capability Map
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-10-26T15:29:33.663Z
updated_at: 2026-10-26T15:29:33.663Z
---
The thin-mirror plan's Capability Map marks these GitHub-web capabilities as Later. Most already have a bead; these do not, so they are recorded here rather than living only in a table in a document.

Covered elsewhere, for reference: the pull-request list and Pulls tab are mb-lnkl, mb-iw1v and mb-cbak (deferred, designed in plan-2026-10-01-github-pulls-tab.md, whose spec bead mb-qftx is closed); SSH acquisition is mb-bi2c.

Not yet tracked anywhere:

- Check and status LOGS. The alpha ships the checks and statuses summary with links out to GitHub for detail; the logs themselves are not fetched or shown.
- GitHub Enterprise hosts. The reducer claims github.com and raw.githubusercontent.com only, and the size check asks github.com whatever GH_HOST names. Supporting an Enterprise host means a host allowlist, per-host credential helper wiring, and per-host canonical sources.
- Inline review-comment anchoring in the diff. Review comments are listed today with their file, line and diff hunk, and a comment's file opens at the served head at its line. Anchoring the thread INTO the diff view is not built. Note that mb-rldc covers anchored threads for the Hosted Review Format, which was removed from the stack in #246 and survives only on the do-not-merge reference branch #247, so it is not the bead for this.
- Blame, releases, and GitHub Actions views. Issues have a hosted-review bead (mb-9rrc) but no thin-mirror one.

None of these blocks the 0.12.0 release: each is an absent capability, not a defect, and nothing in the alpha claims them. File separate beads when any one is picked up; this is the inventory, not a work item.
