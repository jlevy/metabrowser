---
type: is
id: is-01m6f2smr94y9zatyprbsr8dbm
title: "PR #275 A4: Treemap on a not-indexed folder asks for a rollup and gives no reason"
kind: task
status: open
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m6ezt071eh0dj86tf6rct9w6
created_at: 2026-11-02T21:31:40.168Z
updated_at: 2026-11-02T21:55:38.200Z
---
Low, optional suggestion A4 on PR #275 (review https://github.com/jlevy/metabrowser/pull/275#pullrequestreview-5743293650), deferred there. On a not_indexed folder the Treemap tab mounts the rollup controls, requests /api/rollup, gets the 404, logs a console warning on every visit, and shows 'Treemap unavailable.' without the reason File Overview gives. ctx.raw already carries dir.not_indexed. Doing it: share the statement out of file-overview-panel.js, add a branch in renderTreemap that keeps the parent control and asks for nothing, cover it in a session, and add a clause to the CHANGELOG. Waits on a decision whether this goes before the tag.
