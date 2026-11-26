---
type: is
id: is-01m78fw0hdp37ztc29ebfzf2hp
title: Plugin author harness and CI pattern
kind: task
status: open
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
assignee: null
delegate: null
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
hold: null
hold_until: null
created_at: 2026-11-12T18:21:10.060Z
updated_at: 2026-11-26T08:37:20.283Z
started_at: 2026-11-26T08:35:34.380Z
---
Phase 3 (plan: Workflows, CI; Testing Strategy). metabrowser-sdk as a development dependency for type checks and in-process hook tests (it has no dependencies, and is the same package the host injects), a fixture that runs the real worker, the shell's startup scripts and on-demand bundle registry served as data with a golden so browser harnesses stop copying server.py, and the documented CI pattern: metab . --plugin-repo --doctor/--api/--show goldens for editable installs, the same with --plugin-confined on a runner whose kernel has a backend, and a wheel built and installed in a scratch environment checked with metab --plugin-env for libraries that publish wheels.

## Notes

Rewritten 2026-11-26 with the plan's second revision (review against main); supersedes the 2026-11-12 body.
