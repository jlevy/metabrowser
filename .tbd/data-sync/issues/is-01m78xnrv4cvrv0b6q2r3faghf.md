---
type: is
id: is-01m78xnrv4cvrv0b6q2r3faghf
title: "PR #382 A1: a beside badge covers the text after its target (the file name on a file page)"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78xnek6h8yd4znc1a47kdwm
hold: null
hold_until: null
created_at: 2026-11-12T22:22:25.635Z
updated_at: 2026-11-12T22:40:14.987Z
started_at: 2026-11-12T22:22:32.728Z
closed_at: 2026-11-12T22:40:14.986Z
close_reason: "fixed in db6e03ff: beside badge ends at its target's inline end (inset-inline-end: calc(100% - var(--kbd-badge-inline))); test_beside_badges_end_at_their_targets_inline_end; headless Chrome before/after in both themes. Reply: https://github.com/jlevy/metabrowser/pull/382#issuecomment-6837907014"
resolution: null
duplicate_of: null
---
Severity: Medium. PR #382, review A: https://github.com/jlevy/metabrowser/pull/382#pullrequestreview-5882884024. src/metabrowser/static/styles.css:2151-2155 starts a beside badge 2px past its target's inline end (inset-inline-start: calc(var(--kbd-badge-inline) + 2px)), so U covers the file name, mirror note, or path start and Y covers the size or the commit author. Fix: inset-inline-end: calc(100% - var(--kbd-badge-inline)) so the badge sits over the target's own far right, still positioned through the anchor; update the comment at styles.css:2126-2131, docs/design-system.md:1400-1403, CHANGELOG.md:21, QA check 14 (docs/qa-v012-repository-library.md:958), and tests/test_design_vocabulary.py:1951.
