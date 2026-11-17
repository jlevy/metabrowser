---
type: is
id: is-01m7ktd5ba5txphzvehk9b9t2z
title: "PR #494 review A suggestions: CHANGELOG kbd/samp size; parity plan's adapter lines"
kind: task
status: closed
priority: 3
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7ksbsx0kcg5rk05fy23nxc5
hold: null
hold_until: null
created_at: 2026-11-17T03:56:56.553Z
updated_at: 2026-11-17T04:19:33.681Z
started_at: 2026-11-17T03:57:12.202Z
closed_at: 2026-11-17T04:19:33.681Z
close_reason: "Applied on #494: CHANGELOG kbd/samp size (0a888335; popover code changes face only), parity plan notes that KPress 0.3.8 replaced the adapter (58b6b1c1). The synchronous layout read at TOC bind needs no change."
resolution: null
duplicate_of: null
---
Review A suggestions: CHANGELOG.md:11 should say kbd and samp also take KPress's mono size (15px to 12.3px in the probe). docs/project/specs/active/plan-2026-09-10-functional-ui-cli-parity.md:150, :210, :265 still describe the scoped observation adapter; a note that KPress 0.3.8 replaced it. The synchronous layout read at TOC bind needs no change.
