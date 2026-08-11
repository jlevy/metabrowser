---
type: is
id: is-01kzs5y3mbvz1151xyeg83znnj
title: Agent-log event filters drift from shared multi-select controls
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
parent_id: is-01kzrtbtsh9k6p8x84rta84y4p
created_at: 2026-08-11T19:49:03.754Z
updated_at: 2026-08-11T20:12:47.678Z
closed_at: 2026-08-11T20:12:47.677Z
close_reason: Fixed the dynamic agent-log filter state and enforced the shared control-family contract across core markup, styles, SDK documentation, and tests.
---
Claude JSONL event types are classified and filtering works, but the agent-log renderer uses bespoke filter buttons whose selected colors exist for only a fixed set of kinds. Dynamically discovered kinds can therefore toggle without a visible selected-state change. Migrate the event-type chooser to the shared additive multi-select chip contract, preserve counts, ensure aria-pressed and visual state agree for every kind, and cover representative dynamic kinds with behavior and structural tests.

## Notes

Reproduced against the user-supplied Claude JSONL without copying its contents. A dynamically discovered queue-operation filter hid matching events but had identical computed styles before and after and no aria-pressed state. The agent-log view now renders the host's exact joined additive chip group through window.metabrowser.filterControls, preserves counts, humanizes dynamic labels, and disposes shared listeners. All core buttons now carry a documented role primitive; icon-only use sites share icon-btn, the labelled action uses btn, and all core buttons declare type=button. Structural and behavior tests prohibit the legacy private filter family. In-app verification confirmed 11 counted event-type chips, visible pressed/unpressed states, correct hiding, and no console errors. make verify passes with 881 tests.
