---
type: is
id: is-01m7dqrde8130517akbvnbters
title: "Architecture: plugin system and browser shell"
kind: task
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7dqmdjvjrgqd3vpqw3z3zdc
created_at: 2026-11-14T19:15:12.968Z
updated_at: 2026-11-15T08:17:03.384Z
closed_at: 2026-11-15T08:17:03.383Z
close_reason: Implemented on claude/docs-first-principles (one standalone PR)
resolution: null
duplicate_of: null
---
Phase 2, PR 4: plugins and the browser.

- New arch-plugin-system.md (about 300 lines): manifests, discovery, classification, the SDK gate, containers, and how to add a file type end to end (kinds today at arch-views-models-routes.md :994-1011, the rollup family at docs/development.md :408-462, syntax routing only in a file_extensions.py docstring). Copy from arch-nav-containers.md :10-107.
- New arch-browser-shell.md (about 250): app.js and its modules, stores, lifecycle, and asset loading tiers (copy from docs/development.md :147-326; the contributor PR deletes it there). Takes from docs/plugins.md retained-navigation staging (:446-459), the Markdown Worker lifecycle (:849-862), and the diagnostic console tools (:391-399). Fold in the design of plan-2026-07-17-scalable-file-search.md (Quick Search).
- Trim docs/plugins.md (about 800 lines; also cut the SDK-gate reasoning at :884-890, which development.md owns, and "Since SDK 0.6" history at :58) and docs/web-performance-framework.md (about 200).
- Retire arch-nav-containers.md; point the comments in src/ that name it (five files) at the successor.

Known errors to fix:
- arch-nav-containers.md :106-107, :133-135, :170-171 present unbuilt containers as built.
- docs/web-performance-framework.md :15 claims neutrality that static/perf.js:235 contradicts.
