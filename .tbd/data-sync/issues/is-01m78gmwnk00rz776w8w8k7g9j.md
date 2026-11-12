---
type: is
id: is-01m78gmwnk00rz776w8w8k7g9j
title: Checked-in plugin directories under .metabrowser/plugins
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:34:45.298Z
updated_at: 2026-11-12T18:34:45.298Z
---
Phase 2 (plan: Repository Plugins, Discovery and The Repository's Environment). Plugins a repository checks in without packaging: .metabrowser/plugins/<name>/ with manifest.toml, index.js, and optionally sidekick.py. Under trust they load like any repository plugin; their hooks run in a worker on the repository's environment with the plugin directory on sys.path, or, in a repository with no environment, on Metabrowser's own interpreter where only the standard library and the plugin SDK are available. Fixture and goldens for both cases.
