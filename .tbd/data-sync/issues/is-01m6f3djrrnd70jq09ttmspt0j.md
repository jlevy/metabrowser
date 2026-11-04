---
type: is
id: is-01m6f3djrrnd70jq09ttmspt0j
title: "Keyboard: PR rows walk in-page with a held key"
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m2h7jjgpzyfbf10238j32z6q
hold: null
hold_until: null
created_at: 2026-11-02T21:42:33.494Z
updated_at: 2026-11-04T17:14:29.949Z
started_at: 2026-11-03T00:48:47.359Z
closed_at: 2026-11-04T17:14:29.949Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
The user, 2026-11-02: keyboard shortcuts work to navigate the left-hand nav, so it is easy to scroll through PRs. PR rows are a Navigational Row Collection per docs/design-system.md: one Tab stop, Arrow Up and Down and K and J move and open, key repeat stays on, clamped at the ends, no page scroll. Register them in test_nav_like_row_sets_share_the_vertical_keyboard_contract. Help and hint text comes from the command registry, not new key text. Moving between PRs is in-page with no document load and no new server, so holding a key walks the list, and interaction work stays proportional to the change, not the size of the list. Holding a key must not queue a request per row: latest wins, older ones cancelled. Pin in a browserless session with a golden.

## Notes

2026-11-03, PR 285: rows are a Navigational Row Collection, keys in the registry's pull-requests group, registered in test_nav_like_row_sets_share_the_vertical_keyboard_contract. A press opens at once; a held key moves two rows a step and opens the row it stops on, at key-up or WALK_SETTLE_MS; latest wins. Chrome: 200 steps, no request per row, no document load.

2026-11-03 (PR #285 addressing): a key's skim replaces the history entry (A1); a page a held key opened waits to fetch while the key is held (A9); Back or a filter change keeps a row waiting for its record from opening (Qodo r4450241740). Verified in Chrome: a held J kept history.length unchanged and one Back left the rows.
