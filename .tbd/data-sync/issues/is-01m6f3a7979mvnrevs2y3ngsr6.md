---
type: is
id: is-01m6f3a7979mvnrevs2y3ngsr6
title: Panel host and which tab an address shows
kind: task
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m6f3a7pba32qx4tw03bca2tn
parent_id: is-01m2h7jjgpzyfbf10238j32z6q
hold: null
hold_until: null
created_at: 2026-11-02T21:40:43.430Z
updated_at: 2026-11-04T17:14:29.826Z
started_at: 2026-11-03T00:48:45.795Z
closed_at: 2026-11-04T17:14:29.826Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
pulls-nav.js in the shell-tools bundle, registered from the repository context with no request, an onHide hook in the registry, and the Pulls tab active at /pulls and /pull/<n>, including the first page of a pull-request URL. No new startup script.

## Notes

2026-11-03, PR 285: static/pulls-nav.js in shell-tools, listed only in a shell whose root is a GitHub mirror (pulls_tab in server.py), so a folder fetches nothing new. The server draws the tab, and in front at /pull/<n> and /pulls from the first paint. onHide added to the registry; panels keep their own scroll offset. Session tests/dom/pulls-nav-session.js, golden cli-ui-pulls-nav.tryscript.md; shells in tests/test_pulls_nav.py.

2026-11-03 (PR #285 addressing): pulls-nav.js makes its listeners per init (B4), ends a walk only on a walking key's release (A8), and treats each filter of /pulls as its own place for which tab shows (Qodo r4450241750). The page host gained replaceHref for a key's skim (A1).
