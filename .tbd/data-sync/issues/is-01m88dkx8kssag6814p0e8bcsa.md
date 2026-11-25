---
type: is
id: is-01m88dkx8kssag6814p0e8bcsa
title: "PR #811 A9: printing draws every chunk without holding the reader's place"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m88dfdf96exb192c9gb46hfz
hold: null
hold_until: null
created_at: 2026-11-25T03:57:29.221Z
updated_at: 2026-11-25T05:19:27.665Z
started_at: 2026-11-25T03:59:41.586Z
closed_at: 2026-11-25T05:19:27.664Z
close_reason: "Fixed in deba14ccd, test in 95302a957: mountAll draws inside deps.mutate; behavior test checks one hold. https://github.com/jlevy/metabrowser/pull/811#issuecomment-7153635595"
resolution: null
duplicate_of: null
---
Low. diff-markdown.js mountAll 1651-1656, 1872 runs outside deps.mutate. Review A of PR #811: https://github.com/jlevy/metabrowser/pull/811#pullrequestreview-6051579395
