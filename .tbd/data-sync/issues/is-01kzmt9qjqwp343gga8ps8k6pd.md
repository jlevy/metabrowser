---
type: is
id: is-01kzmt9qjqwp343gga8ps8k6pd
title: "PR #24 review R9: Reject malformed Git cursors"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01kzmt94z25m0p0e3g531krnzy
created_at: 2026-08-10T03:08:43.990Z
updated_at: 2026-08-10T03:46:30.175Z
closed_at: 2026-08-10T03:46:30.175Z
close_reason: Fixed in 177e10f and 195b3e1; make verify and GitHub CI passed; all PR review threads replied to and resolved
---
Reject malformed cursors rather than restarting pagination and appending duplicate commits; src/metabrowser/git/routes.py and git_panel.js; thread PRRT_kwDOTX174c6XJ6h8.
