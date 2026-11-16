---
type: is
id: is-01m7hdtsr7w783q875ts3f9hc6
title: "PR #460 A3: the Files tree tooltip drops exact byte counts the size chip rounds"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjgz0543fxmc38m3p8ajk
hold: null
hold_until: null
created_at: 2026-11-16T05:38:43.078Z
updated_at: 2026-11-16T06:14:50.831Z
started_at: 2026-11-16T05:38:55.690Z
closed_at: 2026-11-16T06:14:50.831Z
close_reason: "fixed in cd5ad5682 on claude/tooltips-substantive (PR #460 head b6e2e891d); disposition reply https://github.com/jlevy/metabrowser/pull/460#issuecomment-6908929872"
resolution: null
duplicate_of: null
---
Low. app.js:3286-3306; docs/design-system.md:3477, :3493-3495. Coordinator decision: option (a), keep the exact size when the chip rounds it (1,024 bytes or more), drop it only when the chip shows the same number; update the design system at both places. Review A (senior, round 1) on PR #460: https://github.com/jlevy/metabrowser/pull/460#pullrequestreview-5915440680
