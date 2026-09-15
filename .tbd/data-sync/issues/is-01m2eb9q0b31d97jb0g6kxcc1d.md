---
type: is
id: is-01m2eb9q0b31d97jb0g6kxcc1d
title: "Parity checker: require behavior-function owners and verify function ranges"
kind: task
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-09-10-functional-ui-cli-parity.md
labels:
  - parity
dependencies: []
parent_id: is-01m26hjjvhpcf49p2x1c3390kk
created_at: 2026-09-13T21:38:13.642Z
updated_at: 2026-09-14T23:28:11.873Z
---
From the release senior review (shell/parity lane). Deferred from the v0.9.2 release because each needs a checker redesign, not a local fix.

1. Rows that name factories as owners (catalog-feed.js#create, known-file-catalog.js#create, createLifecycle, createRecentContinuity, create*Coordinator/Client/Budget) are satisfied by any session that merely constructs the object, which is file-level evidence again. Require owners to name the behavior functions a row claims.
2. The Data inputs column only checks that the named routes are registered and covered; nothing checks that the session consumes them (e.g. navigation.route-identity declares /api/file). Either add a consumption check or document precisely what is verified.
3. Coverage credit matches the executed script by filename and full-source UTF-16 length. V8 coverage JSON carries no source text, so a hash is not available from it; consider verifying that each credited function range actually declares its named symbol in the canonical source, handling declarations, methods, and assigned arrows.

## Notes

Deferred from the 2026-09-13 PR round to keep that round short; not started. It rewrites owner entries across the parity table, so start it after the preview-states (mb-8t24/mb-pwt8) and Markdown (mb-k8os) PRs merge, since both add or edit parity rows.
