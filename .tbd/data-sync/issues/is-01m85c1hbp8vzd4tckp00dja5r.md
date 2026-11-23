---
type: is
id: is-01m85c1hbp8vzd4tckp00dja5r
title: "PR #765 A3: choosing Diff or Current does not hold the reader's place inside a file"
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m8577bzvw6qnfffw9g5f56x2
hold: null
hold_until: null
created_at: 2026-11-23T23:32:15.306Z
updated_at: 2026-11-23T23:35:03.210Z
started_at: 2026-11-23T23:35:03.055Z
---
Medium. diff-view.js:1569 (setShow anchors on placeOfTopFile), :1640-1653 (drawShow), :1709-1724, :3117-3162 (holdPlace). The anchor is the file's top, so inside a long file the reader moves by every removed row above. Decision: anchor on the block (Rendered) or line (Source) at the pane's top, falling back to the nearest surviving one; update docs/design-system.md:2549 and docs/reviewing-pull-requests.md:201 and the session geometry test; add a Chrome check with the long-file cases.

Review A on PR #765: https://github.com/jlevy/metabrowser/pull/765#pullrequestreview-6031120972
