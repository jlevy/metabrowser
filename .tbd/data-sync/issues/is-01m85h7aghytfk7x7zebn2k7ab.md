---
type: is
id: is-01m85h7aghytfk7x7zebn2k7ab
title: Align File Overview's legend rail with the README table of contents
kind: bug
status: closed
priority: 2
version: 4
delegate: claude-code@spud10.local
labels: []
dependencies: []
child_order_hints:
  - is-01m85j15gxgp9najr7tq33jtxw
hold: null
hold_until: null
created_at: 2026-11-24T01:02:47.824Z
updated_at: 2026-11-24T02:14:51.017Z
started_at: 2026-11-24T01:02:51.937Z
closed_at: 2026-11-24T02:14:51.015Z
close_reason: null
resolution: null
duplicate_of: null
---
On a wide pane the file-type legend rail and the README TOC share a track but the TOC's content is inset by KPress's .kpress-toc padding (1.2rem/0.7rem), so the legend's dots and names sat 19px left of the TOC's entries. Give the rail the same inset.
