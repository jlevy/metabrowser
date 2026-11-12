---
type: is
id: is-01m76qxjhwjw45ac6542k3f2wn
title: "Binary view: WebKit's forced layout after each content-visibility chunk"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-12T02:03:21.019Z
updated_at: 2026-11-12T02:03:21.019Z
---
From the WebKit gate: after each chunk of content-visibility blocks, WebKit's forced layout takes 70-525 ms against Chrome's under 10 ms (open 1.86-1.99x, Load more 1.39-2.46x, accented 2.1-2.7x). No small fix found yet. Also: the binary view re-renders all loaded chunks 150 ms after the first, because the first ResizeObserver callback sees lastWidth 0.
