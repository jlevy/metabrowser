---
type: is
id: is-01kyh2nydgxp3zse97vam6gsss
title: Sanitize Git-local environment in pre-push verification
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-07-27T06:02:33.263Z
updated_at: 2026-07-27T06:07:32.470Z
closed_at: 2026-07-27T06:07:32.466Z
close_reason: Pre-push hook now clears Git-local environment variables before verification; reproduced under inherited GIT_DIR, real pre-push passed all 748 tests, and repository core.bare remains false.
---
The pre-push hook inherits GIT_DIR and related repository-local variables. Tests that run git init for temporary fixtures then target the real shared Git directory, setting core.bare=true and invalidating gitignore behavior. Clear Git local environment variables before invoking the verification Make targets.
