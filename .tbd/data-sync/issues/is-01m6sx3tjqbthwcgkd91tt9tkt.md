---
type: is
id: is-01m6sx3tjqbthwcgkd91tt9tkt
title: Share watched-file arrival conventions with GitHub catalog updates
kind: feature
status: closed
priority: 2
version: 8
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m6sx9vy43qz7syctdkmhf455
  - type: blocks
    target: is-01m6t2y2ngvnp6r2417kmp3aka
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-07T02:24:01.110Z
updated_at: 2026-11-07T04:55:39.895Z
started_at: 2026-11-07T02:26:48.159Z
closed_at: 2026-11-07T04:55:39.893Z
close_reason: "PR #316 at 3505f4db is mergeable with green exact-head CI and all review threads resolved. Shared one-shot tint, hide cleanup and the design anchor are verified. Conservative clock-skew behavior is documented and tracked separately in mb-irrw."
resolution: null
duplicate_of: null
---
Reuse the existing watched-file row arrival and live-update conventions for newly discovered pull requests and future GitHub-backed collections. Preserve row identity, focus, selection, and scroll anchor. Distinguish provider discoveries from initial load, older paging, and filter changes. Keep retries and connection copy in their existing single status, respect reduced motion, and test bounded visible changes in checkout and managed previews.

## Notes

PR #316 now documents the shared animation at its own layer in 3505f4db, correcting the design anchor. Interrupted highlights clear on hide. Conservative suppression under a machine clock ahead of GitHub is a non-blocking provider-time follow-up mb-irrw. The local-server fetched_at field also uses that clock, so replacing the baseline with fetched_at alone would retain the issue. Regular new rows and controls appear normally.
