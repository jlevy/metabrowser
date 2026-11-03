---
type: is
id: is-01m6f3djrrnd70jq09ttmspt0j
title: "Keyboard: PR rows walk in-page with a held key"
kind: task
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m2h7jjgpzyfbf10238j32z6q
hold: null
hold_until: null
created_at: 2026-11-02T21:42:33.494Z
updated_at: 2026-11-03T04:35:56.160Z
started_at: 2026-11-03T00:48:47.359Z
---
The user, 2026-11-02: keyboard shortcuts work to navigate the left-hand nav, so it is easy to scroll through PRs. PR rows are a Navigational Row Collection per docs/design-system.md: one Tab stop, Arrow Up and Down and K and J move and open, key repeat stays on, clamped at the ends, no page scroll. Register them in test_nav_like_row_sets_share_the_vertical_keyboard_contract. Help and hint text comes from the command registry, not new key text. Moving between PRs is in-page with no document load and no new server, so holding a key walks the list, and interaction work stays proportional to the change, not the size of the list. Holding a key must not queue a request per row: latest wins, older ones cancelled. Pin in a browserless session with a golden.

## Notes

2026-11-03, PR 285: rows are a Navigational Row Collection, keys in the registry's pull-requests group, registered in test_nav_like_row_sets_share_the_vertical_keyboard_contract. A press opens at once; a held key moves two rows a step and opens the row it stops on, at key-up or WALK_SETTLE_MS; latest wins. Chrome: 200 steps, no request per row, no document load.

2026-11-03 (PR #285 addressing): a key's skim replaces the history entry (A1); a page a held key opened waits to fetch while the key is held (A9); Back or a filter change keeps a row waiting for its record from opening (Qodo r4450241740). Verified in Chrome: a held J kept history.length unchanged and one Back left the rows.
