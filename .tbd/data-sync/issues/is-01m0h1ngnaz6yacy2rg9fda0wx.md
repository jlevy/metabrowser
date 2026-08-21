---
type: is
id: is-01m0h1ngnaz6yacy2rg9fda0wx
title: "PR #59 review R6: hook commands lost repository-root anchoring"
kind: bug
status: open
priority: 2
version: 3
labels:
  - upstream-tbd
dependencies: []
parent_id: is-01m0h1neycr90x9zn2evw9vnjq
created_at: 2026-08-21T02:16:14.250Z
updated_at: 2026-08-21T02:28:50.456Z
---
PR #59 review R6 (Medium). .claude/settings.json and .codex/hooks.json invoke 'bash .claude/...' and 'bash .codex/...' with no root anchoring, so a session whose cwd is not the repository root runs nothing. Previously anchored with $CLAUDE_PROJECT_DIR and $(git rev-parse --show-toplevel); the anchoring is not what tbd generates. Documented in docs/development.md rather than re-patched. Fix belongs in tbd's generator.
