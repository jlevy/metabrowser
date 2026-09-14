---
type: is
id: is-01m2f0dtwk26wzsa8hqmmxej71
title: "PR #113 review suggestions: parity row inputs, design-system dangling spinner reference, and other nits"
kind: task
status: closed
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m2f0dryv9qmyp9y6g1sc4gwq
created_at: 2026-09-14T03:47:28.786Z
updated_at: 2026-09-14T04:40:33.767Z
closed_at: 2026-09-14T04:40:33.766Z
close_reason: "Applied in d454320f: transport-exempt:/api/events parity input, design-system reorder, 'is not reachable' copy, palette reconnected() clears connection status, module-scoped pytest fixture, server.py vs previewPlaceholderHtml markup check, MetabrowserPreviewPanePhase."
resolution: null
duplicate_of: null
---
PR #113 review suggestions (non-blocking): (1) add transport-exempt:/api/events to navigation.preview-pane-states row in docs/project/architecture/arch-views-models-routes.md:261; (2) docs/design-system.md:1878 'holding that neutral spinner' refers to a spinner introduced later; (3) UNREACHABLE_SUMMARY contraction; (4) stale Quick File status after reconnect; (5) module-scoped fixture in tests/test_preview_pane_state_js.py; (6) pytest comparing shell spinner markup to previewPlaceholderHtml; (7) name MetabrowserPreviewPanePhase in types.d.ts. Apply cheap ones, note the rest.
