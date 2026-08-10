---
type: is
id: is-01kzmt9nqt24sxmnqhedbvwc27
title: "PR #24 review R1: Prevent cross-owner preview races"
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
parent_id: is-01kzmt94z25m0p0e3g531krnzy
created_at: 2026-08-10T03:08:42.105Z
updated_at: 2026-08-10T03:46:30.064Z
closed_at: 2026-08-10T03:46:30.063Z
close_reason: Fixed in 177e10f and 195b3e1; make verify and GitHub CI passed; all PR review threads replied to and resolved
---
Fix the shell preview ownership race at src/metabrowser/static/git_panel.js:469; thread PRRT_kwDOTX174c6XusNO.
