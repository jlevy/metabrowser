---
type: is
id: is-01kzwhme4gyzm3akfkd83vh2sw
title: Validate keyboard Help and navigation end to end
kind: task
status: open
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md
labels: []
dependencies: []
parent_id: is-01kzwhmcj1b9fngz4nj21p1p7e
created_at: 2026-08-13T03:11:13.039Z
updated_at: 2026-08-13T04:08:29.783Z
---
Validate the complete feature at DOM, HTML, package, and real-browser levels. Add tests/test_browser_keyboard_js.py for the new Node suites; expand tests/test_quick_file_integration.py and tests/test_browser_recent_ui.py for full script order, one dispatcher, injected dependencies, old-listener/table removal, hint-host placement, unchanged polite progress, and the dedicated owned-group tree wrapper with level/position/set metadata. Update devtools/check_distribution.py so all four modules are required resources in wheel and sdist smoke checks. Use public manual fixtures to check exact Help/link/copy and cross-surface bindings, valid-or-omitted physical-key ARIA, trigger state, modal inert/focus lifecycle, contextual availability, lazy/paged/live focus repair, native preview scrolling, narrow panes, 200% zoom, both themes, reduced motion, keyboard-only operation, and console cleanliness. Update README.md with ? Help, persistent hints, and tree navigation; run public hygiene and make verify.
