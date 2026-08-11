---
type: is
id: is-01kzsbeh7nmvevgsmyr9w174d5
title: Make agent-log surfaces fully theme-aware
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01kzrtbtsh9k6p8x84rta84y4p
created_at: 2026-08-11T21:25:24.852Z
updated_at: 2026-08-11T21:34:11.333Z
closed_at: 2026-08-11T21:34:11.332Z
close_reason: Agent-log summary, record headers, and kind badges now use plugin-owned theme tokens with dark overrides. Unknown kinds and all error kinds are styled consistently; contrast and ownership tests pass in both themes; make verify passed.
---
The Claude/agent JSONL renderer mixes light components into dark mode. Record chevron headers and summary tallies use light backgrounds while the surrounding page is dark. Audit the complete agent-log surface, move plugin-specific visual rules into the plugin stylesheet, use semantic theme tokens consistently, and verify both light and dark themes without changing public APIs or file formats.
