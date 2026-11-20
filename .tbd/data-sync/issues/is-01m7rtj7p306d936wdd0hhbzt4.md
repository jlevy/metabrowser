---
type: is
id: is-01m7rtj7p306d936wdd0hhbzt4
title: "View on GitHub: working-tree counterpart follow-ups from #595 review B"
kind: task
status: open
priority: 3
version: 4
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m7wysqjj7ps8vx91xva66k54
created_at: 2026-11-19T02:35:54.946Z
updated_at: 2026-11-20T17:16:50.774Z
---
From review B on #595 (attic/landing/reviews/pr595-senior-r2.txt): B1 after a local rebase onto newer origin/main with a stale upstream, the working tree maps at the old fork point, so files new on main lose the button; prefer the newest commit origin has. B2 HEAD-ahead path runs 4-6 git processes in sequence per page, unmeasured and uncached between pages, and gather leaves the other half running after a failure; measure, cache per HEAD, cancel siblings. B3 docs/design-system.md:520 and :2158-2159 still list View on GitHub among a pull request's ages.

## Notes

Also from #595's final report: (1) a checkout --ref pin maps only when origin has its commit; the merge-base fallback covers the working tree only. (2) A clone with neither an upstream nor origin/HEAD gets no button on its working tree. (3) The header's data-path attribute is no longer read by production code (grep); remove it or use it. (4) test_page_header_chrome's 48 s bound failed locally at load average 138; CI passed. (5) Doc mismatch: qa-macos-app-hand-checks.md Files check 11 says 'A file you have edited and not committed shows none', but changelog.d/mb-4wqh.md and design-system.md:963 say local edits link to the pushed version. Correct check 11.
