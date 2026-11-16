---
type: is
id: is-01m7hhgmkd61hq9h61js7p43a8
title: "PR #474 A1: Files filter remark and outside-folder count numbers become flex items"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hg857dzfenxr1hee0jd9ka
hold: null
hold_until: null
created_at: 2026-11-16T06:43:04.429Z
updated_at: 2026-11-16T06:43:13.181Z
started_at: 2026-11-16T06:43:13.180Z
---
Medium. src/metabrowser/static/app.js:6030-6042, :6079-6081; styles.css:3720-3725; git-panel.js:2604-2609; styles.css:6782-6787. paintCountParts paints into the flex .nav-metadata line, so spacing and innerText/accessibility text split. Fix: paint into one inline span; add a Chrome invariant. Review A round 1 on PR #474: https://github.com/jlevy/metabrowser/pull/474#pullrequestreview-5915978133
