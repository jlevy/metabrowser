---
type: is
id: is-01m0nvhcawrbzk5511exhn8xeb
title: "PR #66 review F6: inline rows stranded when the tree fetch throws"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m0nvgqxqbb35etfxh3xbbkh9
created_at: 2026-08-22T23:05:19.452Z
updated_at: 2026-08-22T23:16:36.102Z
closed_at: 2026-08-22T23:16:36.101Z
close_reason: "Fixed: loadTree wraps the fetch and the json parse in try/catch and routes both failure kinds into the same error render as a non-ok status, via a shared failTree helper."
---
app.js:788-800. The !resp.ok path renders the error, but a network failure or resp.json() parse error THROWS and nothing in loadTree catches it. The reader is left with 200 painted rows, no chrome, no counts, no truncation affordance, and no error — a tree that looks complete and is not. Before the inline the same failure left an empty pane, which at least reads as broken. Fix: try/catch the fetch and parse, route both into the existing error render.
