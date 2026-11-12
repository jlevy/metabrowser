---
type: is
id: is-01m77bbymqdmjexeq490ev38hs
title: Commit a WKWebView measurement probe under explorations/performance-loop
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T07:43:15.094Z
updated_at: 2026-11-12T07:43:15.094Z
---
A measurement instrument, not app code: a small Swift WKWebView harness committed under explorations/performance-loop (beside the transition scenario, mb-4z4u) that records relaunch and reload request counts through a logging proxy, hidden first-view completion, and show-to-ready in a visible window on an unlocked screen. The research's harness (wkprobe) was ad hoc and is not committed; the WebKit gate harness on the native stack (#363, mb-gvtw) is app code and stays unmerged. Blocks H97 (mb-touu) and the WKWebView secondary metric of H87 (mb-3m3l, which also needs mb-qzny's sticky port), and the WKWebView request counts in the campaign summary (mb-ep8a). From review A on jlevy/metabrowser#364, finding A10.
