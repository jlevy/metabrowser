---
type: is
id: is-01kzmt9r1fzwqdyn9kr6zg35f2
title: "PR #24 review R11: Retry history when Git tab reopens"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01kzmt94z25m0p0e3g531krnzy
created_at: 2026-08-10T03:08:44.462Z
updated_at: 2026-08-10T03:46:30.187Z
closed_at: 2026-08-10T03:46:30.187Z
close_reason: Fixed in 177e10f and 195b3e1; make verify and GitHub CI passed; all PR review threads replied to and resolved
---
Retry a failed initial Git history load when the tab is activated again; src/metabrowser/static/app.js:1846 and git_panel.js; thread PRRT_kwDOTX174c6Xuriu.
