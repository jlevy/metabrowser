---
type: is
id: is-01m78fw11hmhxr4skq16793f7t
title: Run third-party Python only out of process
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:10.576Z
updated_at: 2026-11-12T21:17:51.661Z
---
Phase 5 (plan: Principles, Rollout Plan; Key Decision 6). Only after the three downstream plugins have run in workers for a release: entry points installed into Metabrowser's own environment run in a worker on Metabrowser's interpreter, the in-process sidekick path for third-party plugins goes behind the gate, and metabrowser.plugin_api refuses to import outside a running server or a worker. Not on Windows until a Windows worker exists. docs/plugins.md and the Standing Compatibility Answers describe the result; CHANGELOG.md announces it.

## Notes

Body rewritten 2026-11-12 after the Fable 5.2 design review; it supersedes the earlier review notes. The plan's Key Decisions are awaiting the owner.
