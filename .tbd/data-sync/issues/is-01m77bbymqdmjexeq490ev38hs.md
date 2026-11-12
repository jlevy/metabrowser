---
type: is
id: is-01m77bbymqdmjexeq490ev38hs
title: Commit a WKWebView measurement probe under explorations/performance-loop
kind: task
status: in_progress
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m774ra6cpn1h8jnk2mkzq0nh
  - type: blocks
    target: is-01m774rfn15h0t9ys9eg0nvgyx
  - type: blocks
    target: is-01m784mz5kd9vnjhbchmkaa6e0
parent_id: is-01m774q0ep0jq6vhb790rart0v
hold: null
hold_until: null
created_at: 2026-11-12T07:43:15.094Z
updated_at: 2026-11-12T15:05:04.946Z
started_at: 2026-11-12T08:48:32.561Z
---
A measurement instrument, not app code: a small Swift WKWebView harness committed under explorations/performance-loop (beside the transition scenario, mb-4z4u) that records relaunch and reload request counts through a logging proxy, hidden first-view completion, and show-to-ready in a visible window on an unlocked screen. The research's harness (wkprobe) was ad hoc and is not committed; the WebKit gate harness on the native stack (#363, mb-gvtw) is app code and stays unmerged. Blocks H97 (mb-touu) and the WKWebView secondary metric of H87 (mb-3m3l, which also needs mb-qzny's sticky port), and the WKWebView request counts in the campaign summary (mb-ep8a). From review A on jlevy/metabrowser#364, finding A10.

## Notes

Probe committed on claude/perf-wkprobe (cc5f3208), draft PR. Visible validation blocked: the screen was locked all session; every run correctly refused by the screen guard. Run 'node explorations/performance-loop/wkprobe.mjs run ... --wait-for-screen 3600' once unlocked.
