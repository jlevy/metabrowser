---
type: is
id: is-01kzsc71m2gs2sgsjheqemj7v2
title: Fix wrapped agent-log toggle group geometry
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01kzrtbtsh9k6p8x84rta84y4p
created_at: 2026-08-11T21:38:48.065Z
updated_at: 2026-08-11T21:46:51.567Z
closed_at: 2026-08-11T21:46:51.566Z
close_reason: "Replaced the wrapped segmented control with the standard wrapping filter-chip pattern: the semantic group is borderless, each native button owns its pill boundary and ARIA pressed state, the joined layout stays single-row, the plugin SDK type and design-system contract are documented, live dark-mode geometry was verified, and make verify passes with 886 tests plus 28 golden cases."
---
The agent-log event-type multi-select renders all wrapped rows inside one oversized rounded frame while each button remains square. Reproduce the layout, redesign the shared wrapped chip-group geometry with non-interactive row end caps or an equivalent semantic treatment, preserve accessible button behavior, document the control contract, and verify narrow and wide layouts in both themes.
