---
type: is
id: is-01m88dkrhde4p4717m9ry401rx
title: "PR #811 A8: askMore's 429 retry wait is a timer nothing cancels"
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
created_at: 2026-11-25T03:57:24.394Z
updated_at: 2026-11-25T05:19:20.211Z
started_at: 2026-11-25T03:59:39.805Z
closed_at: 2026-11-25T05:19:20.204Z
close_reason: "Fixed in deba14ccd: the 429 retry wait ends on abort and cancels its timer; behavior test case. https://github.com/jlevy/metabrowser/pull/811#issuecomment-7153635595"
resolution: null
duplicate_of: null
---
Low. diff-markdown.js 1099-1101: the later() handle is not kept, so dispose cannot cancel it and the loop loads once more after disposal. Review A of PR #811: https://github.com/jlevy/metabrowser/pull/811#pullrequestreview-6051579395
