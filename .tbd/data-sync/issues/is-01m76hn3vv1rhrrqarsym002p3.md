---
type: is
id: is-01m76hn3vv1rhrrqarsym002p3
title: Run and record the WebKit measurement gate in the app
kind: task
status: in_progress
priority: 1
version: 11
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m75sajkrdqname9cgrtcf9jf
  - type: blocks
    target: is-01m75sahhp1nbm15h57bjb9bvp
  - type: blocks
    target: is-01m75saj4h7s3trg7kt812fbya
  - type: blocks
    target: is-01m748xta3y5hxhf6kx1n8psja
  - type: blocks
    target: is-01m76cd1ysrge9arg7a773j3ff
  - type: blocks
    target: is-01m748xs18re0g14ge32270n3e
  - type: blocks
    target: is-01m748xswj3y4wnc6bfb60kmp6
  - type: blocks
    target: is-01m76h3hdcp0ek254274recmn5
  - type: blocks
    target: is-01m76cd0j37s7vbfjfwtw1ey7n
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T00:13:52.378Z
updated_at: 2026-11-12T00:37:47.992Z
started_at: 2026-11-12T00:37:47.991Z
---
v1 milestone, before the shell grows further (review A1 on jlevy/metabrowser#357). The 2026-11-08 packaging brief keeps the Swift WKWebView shell only if WebKit passes a measurement gate against the Chrome-measured large-content bounds (docs/large-content-rendering.md); otherwise Electron. Run those measured cases in the app's WKWebView, record results beside the Chrome numbers with the method, and check window.print() and drag and drop by hand. mb-etqi keeps the broader owner acceptance (browser matrix, private auth, external plugin).
