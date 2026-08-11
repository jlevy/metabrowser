---
type: is
id: is-01kzmt9qbc7bfc5tmbe2ze5w4x
title: "PR #24 review R8: Refresh repositories after first commit"
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
parent_id: is-01kzmt94z25m0p0e3g531krnzy
created_at: 2026-08-10T03:08:43.755Z
updated_at: 2026-08-10T03:46:30.169Z
closed_at: 2026-08-10T03:46:30.169Z
close_reason: Fixed in 177e10f and 195b3e1; make verify and GitHub CI passed; all PR review threads replied to and resolved
---
Prevent cached unborn state and one-shot panel loading from hiding a repository's first commit; src/metabrowser/git/routes.py:133 and git_panel.js; thread PRRT_kwDOTX174c6XJ6h4.
