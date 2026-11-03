---
type: is
id: is-01m6g1xkxg27v3g4dry1g3be7z
title: "PR #285 C2: a poll's whole-range read that does not land leaves the new tag over the old rows"
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6g1x4rv0qbdqdqdz64p3qn0
created_at: 2026-11-03T06:35:36.239Z
updated_at: 2026-11-03T06:35:36.239Z
---
builtin_plugins/github/pulls-panel.js:741 stores the top window's etag before holdContent (:744) reads the whole held range; an abort, a throw, or holdContent's filter return leave the tag over old rows, and later polls 304. Take the tag only with the rows; add a session step. Review: https://github.com/jlevy/metabrowser/pull/285#pullrequestreview-5747624823 (severity Low).
