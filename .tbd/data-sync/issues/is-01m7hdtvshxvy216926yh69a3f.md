---
type: is
id: is-01m7hdtvshxvy216926yh69a3f
title: "PR #460 A7: the Files Chrome tooltip probe's 450 and 250 ms waits are coupled to the tooltip delays unnamed"
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
created_at: 2026-11-16T05:38:45.168Z
updated_at: 2026-11-16T06:14:51.220Z
started_at: 2026-11-16T05:38:57.490Z
closed_at: 2026-11-16T06:14:51.219Z
close_reason: "fixed in cd5ad5682 on claude/tooltips-substantive (PR #460 head b6e2e891d); disposition reply https://github.com/jlevy/metabrowser/pull/460#issuecomment-6908929872"
resolution: null
duplicate_of: null
---
Low suggestion. tests/dom/files-tab-chrome.mjs:188, :200 vs app.js:2980-2981 TOOLTIP_APPEAR_DELAY and TOOLTIP_FADE_OUT. Poll or name the coupling. Review A (senior, round 1) on PR #460: https://github.com/jlevy/metabrowser/pull/460#pullrequestreview-5915440680
