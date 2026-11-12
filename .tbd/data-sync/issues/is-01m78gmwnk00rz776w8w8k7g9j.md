---
type: is
id: is-01m78gmwnk00rz776w8w8k7g9j
title: Checked-in plugin directories under .metabrowser/plugins
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:34:45.298Z
updated_at: 2026-11-12T21:17:46.267Z
---
Phase 3 (plan: Checked-In Plugin Directories; Key Decision 3). A directory under .metabrowser/plugins/<name>/ is a provider. Its Python runs in the clone's worker, each plugin's modules loaded from its own directory under a package name of its own (no shared sys.path entry, so sidekick.py files neither collide nor shadow the environment). In a clone with no environment, its hooks run in a worker on Metabrowser's base interpreter started with -I -S, where only the standard library and the injected runtime are importable (verified: -I -S finds none of Starlette, Pydantic, Softschema, or Metabrowser). Fixture and goldens for both cases.

## Notes

Body rewritten 2026-11-12 after the Fable 5.2 design review; it supersedes the earlier review notes. The plan's Key Decisions are awaiting the owner.
