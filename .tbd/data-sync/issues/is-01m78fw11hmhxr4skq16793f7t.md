---
type: is
id: is-01m78fw11hmhxr4skq16793f7t
title: Run third-party Python only out of process
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:10.576Z
updated_at: 2026-11-12T18:47:18.743Z
---
Phase 2 (plan: Principles, Process Model, Rollout Plan). Entry points installed into Metabrowser's own environment run in a worker on Metabrowser's interpreter; remove the in-process sidekick import for non-built-in plugins and the sidekick names from metabrowser.__all__, behind the gate; rewrite docs/plugins.md Trust Model and Discovery, Packaging a Python Plugin, and Python Sidekick API; announce in CHANGELOG.md. Built-ins stay in process.

## Notes

Review (2026-11-12, independent design review; plan updated to match): metabrowser.plugin_api should refuse to import outside a running server, so a worker on Metabrowser's own interpreter cannot bind helpers to ROOT_DIR = Path().
