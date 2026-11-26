---
type: is
id: is-01m78gmwnk00rz776w8w8k7g9j
title: Checked-in plugin directories under .metabrowser/plugins
kind: task
status: open
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
assignee: null
delegate: null
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
hold: null
hold_until: null
created_at: 2026-11-12T18:34:45.298Z
updated_at: 2026-11-26T08:37:20.288Z
started_at: 2026-11-26T08:35:34.387Z
---
Phase 4 (plan: Checked-In Plugin Directories; Key Decision 3). A directory under .metabrowser/plugins/<name>/ in the clone's primary worktree is a provider; a linked worktree's copy is never read, so code an agent edits there does not run and a folder that forges a link to a trusted clone brings no code. Its Python runs in the clone's worker, each plugin's modules loaded from its own directory under a package name of its own (no shared sys.path entry, so sidekick.py files neither collide nor shadow the environment). In a clone with no environment, its hooks run in a worker on Metabrowser's base interpreter started with -I -S, where only the standard library and the runtime are importable (reproduced twice). This is the case where the consent is the only gate, so it runs confined by default. Fixture and goldens for both cases.

## Notes

Rewritten 2026-11-26 with the plan's second revision (review against main); supersedes the 2026-11-12 body.
