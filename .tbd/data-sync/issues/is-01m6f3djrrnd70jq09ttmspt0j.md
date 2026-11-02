---
type: is
id: is-01m6f3djrrnd70jq09ttmspt0j
title: "Keyboard: PR rows walk in-page with a held key"
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m2h7jjgpzyfbf10238j32z6q
created_at: 2026-11-02T21:42:33.494Z
updated_at: 2026-11-02T21:42:33.494Z
---
The user, 2026-11-02: keyboard shortcuts work to navigate the left-hand nav, so it is easy to scroll through PRs. PR rows are a Navigational Row Collection per docs/design-system.md: one Tab stop, Arrow Up and Down and K and J move and open, key repeat stays on, clamped at the ends, no page scroll. Register them in test_nav_like_row_sets_share_the_vertical_keyboard_contract. Help and hint text comes from the command registry, not new key text. Moving between PRs is in-page with no document load and no new server, so holding a key walks the list, and interaction work stays proportional to the change, not the size of the list. Holding a key must not queue a request per row: latest wins, older ones cancelled. Pin in a browserless session with a golden.
