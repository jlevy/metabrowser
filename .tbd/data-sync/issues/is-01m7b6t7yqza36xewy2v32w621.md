---
type: is
id: is-01m7b6t7yqza36xewy2v32w621
title: "JSON view: render (12–14 ms) and layout (about 25 ms) put its first paint on a frame boundary"
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-13T19:40:38.230Z
updated_at: 2026-11-13T19:40:38.230Z
---
In the cold JSON view (`package-lock.json` in the transition scenario), the task that
renders the view after its data arrives takes 12.0–14.3 ms: a microtask checkpoint with
about 4–5 ms of forced layout. A layout and paint frame of about 25 ms follows it, with
about 14 ms of layout. Together they put first paint right on a frame boundary.

When the render task starts by about 27 ms after the click, the view paints at about
63–65 ms. When it slips to 31 ms or later, the view paints at about 80 ms. A vsync frame
task landing between the data response and its body finishing, or a server stall of a few
milliseconds earlier in the chain, is enough to cause the slip. diag083 (2026-11-13) saw
this in every build: control 1 of 4, #372's candidate 2 of 4, and a Server-Timing-off
variant 3 of 4. It is why `files.cold.json` reads as one frame later in exp-083 (exp-087
re-tests that).

Fix: cut the render or layout cost, for example by rendering the tree's first screen only
or deferring off-screen rows, so the first paint is clear of the boundary. Then measure
painted ready and its frame count on a cold JSON view, interleaved, with the share of
runs that land on the later frame.
