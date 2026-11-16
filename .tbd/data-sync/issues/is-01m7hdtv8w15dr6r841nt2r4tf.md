---
type: is
id: is-01m7hdtv8w15dr6r841nt2r4tf
title: "PR #460 A6: compute a crumb's displayPath once in headerAddressHtml"
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
created_at: 2026-11-16T05:38:44.635Z
updated_at: 2026-11-16T06:14:52.420Z
started_at: 2026-11-16T05:38:57.111Z
closed_at: 2026-11-16T06:14:52.420Z
close_reason: "fixed in bbd9915bf on claude/tooltips-substantive (PR #460 head b6e2e891d); disposition reply https://github.com/jlevy/metabrowser/pull/460#issuecomment-6908929872"
resolution: null
duplicate_of: null
---
Low suggestion. src/metabrowser/static/app.js:356 writes esc(displayPath(segments[i])) twice; compute once so tip and text cannot drift. Review A (senior, round 1) on PR #460: https://github.com/jlevy/metabrowser/pull/460#pullrequestreview-5915440680
