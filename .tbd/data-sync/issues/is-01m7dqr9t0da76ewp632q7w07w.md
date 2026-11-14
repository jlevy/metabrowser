---
type: is
id: is-01m7dqr9t0da76ewp632q7w07w
title: "Docs: browsing-files and keyboard-shortcuts guides"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7dqmd3wafkq2x9r1y2gt57v
created_at: 2026-11-14T19:15:09.247Z
updated_at: 2026-11-14T19:15:09.247Z
---
Phase 1, PR 4. The only phase-1 editor of docs/design-system.md and docs/realtime-debugging.md.

- New docs/browsing-files.md (about 250 lines): the Files tab (tree, Overview, Treemap, Recent, filters); reading Markdown (wiki links, transclusion), data, code, logs, images, and HTML; live updates and log tailing (/api/stream); Quick Search for files; remote hosts as a workflow (options live in command-line.md). Move the user parts of docs/realtime-debugging.md here.
- New docs/keyboard-shortcuts.md (about 100 lines): the user table from design-system.md's Keyboard Shortcuts section, with the tests/test_keymap.py pin (around :271) moving to the new file. design-system.md keeps the design rules and links it; README:125 points here.
- Fix the header comment of src/metabrowser/static/main-tabs.js: it says Files, Commits, and Pulls; MAIN_TABS order is Files, Pulls, Commits.
- Add README links.
