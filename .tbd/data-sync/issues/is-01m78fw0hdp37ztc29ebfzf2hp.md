---
type: is
id: is-01m78fw0hdp37ztc29ebfzf2hp
title: Plugin author harness and CI pattern
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:10.060Z
updated_at: 2026-11-12T21:17:42.960Z
---
Phase 2 (plan: Workflows, CI; Testing Strategy). A published copy of the injected runtime for type checks and in-process hook tests (name must not match the metabrowser-plugin-<name> pattern; release mechanics per the plan's Open Questions), a fixture that runs the real worker, the shell's startup scripts and on-demand bundle registry served as data with a golden so browser harnesses stop copying server.py, and the documented CI pattern: metab-plugins . --repo --doctor/--api/--show goldens for editable installs, plus a wheel built and installed in a scratch environment checked with metab-plugins --env for libraries that publish wheels.

## Notes

Body rewritten 2026-11-12 after the Fable 5.2 design review; it supersedes the earlier review notes. The plan's Key Decisions are awaiting the owner.
