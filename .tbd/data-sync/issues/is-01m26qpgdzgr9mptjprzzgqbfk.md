---
type: is
id: is-01m26qpgdzgr9mptjprzzgqbfk
title: Close queued Recent repaint and resync races
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m0hhjf2e1w8tp30ay4tj8183
created_at: 2026-09-10T22:41:00.337Z
updated_at: 2026-09-10T22:44:43.858Z
closed_at: 2026-09-10T22:44:43.856Z
close_reason: Implemented generation- and identity-guarded Recent repaint cancellation plus bounded resync repair; exact browserless session/golden coverage added; full make verify passed with 1972 pytest and 105 golden tests.
resolution: null
duplicate_of: null
---
Final release seam review found two stale-view races: a debounced Recent overlay repaint could run after a newer filter/source transition, and fs.resync_required did not invalidate an in-flight or settled Recent snapshot. Add identity-guarded cancellation, route resync through bounded continuity repair, and pin both cases in the exact browserless CLI golden.
