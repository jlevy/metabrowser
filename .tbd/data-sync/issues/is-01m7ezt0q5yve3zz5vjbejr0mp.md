---
type: is
id: is-01m7ezt0q5yve3zz5vjbejr0mp
title: "U1: what a kept surface costs in WKWebView — toggle against re-attach on three surfaces, footprint per surface"
kind: task
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-14-performance-campaigns.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-15T06:55:08.516Z
updated_at: 2026-11-15T07:26:42.198Z
---
Architecture review uncertainty U1, read before H112's round. WebKit lays out 1.1 to 5 times slower than Chrome (docs/large-content-rendering.md), so H112's tiers, and whether a detached tier is worth having, depend on this reading. Instrument: wkprobe-steps.mjs. Lane W: needs the user present at an unlocked screen.

## Notes

2026-11-15 (#441 re-review): the instrument does not exist yet. wkprobe-steps.mjs only attributes requests to steps; this reading needs a toggle-against-re-attach scenario in wkprobe (three surfaces, with the footprint per surface) built before the Lane W session.
