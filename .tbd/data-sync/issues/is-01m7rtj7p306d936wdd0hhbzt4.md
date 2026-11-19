---
type: is
id: is-01m7rtj7p306d936wdd0hhbzt4
title: "View on GitHub: working-tree counterpart follow-ups from #595 review B"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-19T02:35:54.946Z
updated_at: 2026-11-19T02:35:54.946Z
---
From review B on #595 (attic/landing/reviews/pr595-senior-r2.txt): B1 after a local rebase onto newer origin/main with a stale upstream, the working tree maps at the old fork point, so files new on main lose the button; prefer the newest commit origin has. B2 HEAD-ahead path runs 4-6 git processes in sequence per page, unmeasured and uncached between pages, and gather leaves the other half running after a failure; measure, cache per HEAD, cancel siblings. B3 docs/design-system.md:520 and :2158-2159 still list View on GitHub among a pull request's ages.
