---
type: is
id: is-01m0h1ngnaz6yacy2rg9fda0wx
title: "PR #59 review R6: hook commands lost repository-root anchoring"
kind: bug
status: closed
priority: 2
version: 4
labels:
  - upstream-tbd
dependencies: []
parent_id: is-01m0h1neycr90x9zn2evw9vnjq
created_at: 2026-08-21T02:16:14.250Z
updated_at: 2026-08-21T05:40:30.981Z
closed_at: 2026-08-21T05:40:30.981Z
close_reason: "Confirmed by Joshua 2026-08-21: follow tbd's standard installation on the latest version. These are consequences of committing generated output as generated, documented in docs/development.md, and not defects in this repository. Verified zero drift: 'tbd setup --auto' produces no diff. Any fix belongs in tbd's generator."
---
PR #59 review R6 (Medium). .claude/settings.json and .codex/hooks.json invoke 'bash .claude/...' and 'bash .codex/...' with no root anchoring, so a session whose cwd is not the repository root runs nothing. Previously anchored with $CLAUDE_PROJECT_DIR and $(git rev-parse --show-toplevel); the anchoring is not what tbd generates. Documented in docs/development.md rather than re-patched. Fix belongs in tbd's generator.
