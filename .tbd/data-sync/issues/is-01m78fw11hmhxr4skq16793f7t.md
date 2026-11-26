---
type: is
id: is-01m78fw11hmhxr4skq16793f7t
title: Run third-party Python only out of process
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
created_at: 2026-11-12T18:21:10.576Z
updated_at: 2026-11-26T08:37:20.294Z
started_at: 2026-11-26T08:35:34.397Z
---
Phase 5 (plan: Principles, Rollout Plan; Key Decision 6). Only after the three downstream plugins have run in workers for a release: entry points installed into Metabrowser's own environment run in a worker on Metabrowser's interpreter, and the in-process sidekick path for third-party plugins goes. Not on Windows until a Windows worker exists. docs/plugins.md, arch-plugin-system.md, and the Standing Compatibility Answers describe the result; a changelog fragment announces it.

## Notes

Rewritten 2026-11-26 with the plan's second revision (review against main); supersedes the 2026-11-12 body.
