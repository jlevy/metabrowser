---
type: is
id: is-01m78gmwnk00rz776w8w8k7g9j
title: Checked-in plugin directories under .metabrowser/plugins
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:34:45.298Z
updated_at: 2026-11-12T18:47:18.326Z
---
Phase 2 (plan: Repository Plugins, Discovery and The Repository's Environment). Plugins a repository checks in without packaging: .metabrowser/plugins/<name>/ with manifest.toml, index.js, and optionally sidekick.py. Under trust they load like any repository plugin; their hooks run in a worker on the repository's environment with the plugin directory on sys.path, or, in a repository with no environment, on Metabrowser's own interpreter where only the standard library and the plugin SDK are available. Fixture and goldens for both cases.

## Notes

Review (2026-11-12, independent design review; plan updated to match): No fallback to Metabrowser's own environment (it holds all of Metabrowser's dependencies and an importable metabrowser.plugin_api bound to the wrong root): without a repository environment a checked-in plugin is JavaScript-only. Load each checked-in plugin's modules from its own directory under a unique package name, never via a shared sys.path entry.
