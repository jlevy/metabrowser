---
type: is
id: is-01m7k5kjf3pyy8hyf0jcv29dgq
title: "PR #485 A15: The DMG's compression level is not reconciled with the Apple guidance the plan quotes"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T21:53:26.498Z
updated_at: 2026-11-16T22:10:02.846Z
started_at: 2026-11-16T21:53:41.471Z
closed_at: 2026-11-16T22:10:02.844Z
close_reason: "Fixed in 83ef69fc3: the plan reads Apple's guidance as allowing UDZO and builds at hdiutil's default zlib level; mb-4hwg measures both and records the choice in make-dmg.sh."
resolution: null
duplicate_of: null
---
Low. PLAN:218-221, :295; apps/macos/scripts/make-dmg.sh:64. Fix: state the reading or use the default zlib level, and record the choice in make-dmg.sh. Review A (round 1) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5928293258
