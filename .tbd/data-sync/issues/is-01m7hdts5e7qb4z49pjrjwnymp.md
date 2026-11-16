---
type: is
id: is-01m7hdts5e7qb4z49pjrjwnymp
title: "PR #460 A2: no test checks that the shell applies the tooltip rule in showTipText"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjgz0543fxmc38m3p8ajk
hold: null
hold_until: null
created_at: 2026-11-16T05:38:42.477Z
updated_at: 2026-11-16T06:14:50.460Z
started_at: 2026-11-16T05:38:55.300Z
closed_at: 2026-11-16T06:14:50.460Z
close_reason: "fixed in bc0e1537a on claude/tooltips-substantive (PR #460 head b6e2e891d); disposition reply https://github.com/jlevy/metabrowser/pull/460#issuecomment-6908929872"
resolution: null
duplicate_of: null
---
Medium. tests/dom/github-pull-header-chrome.mjs:573-614, :912-918 lift tipAddsInformation; app.js:3148-3152 showTipText; tests/dom/shell-delegate-owner-session.js:190, :233 check names overclaim. Fix: probe the document's own mouseenter listener and read .custom-tooltip after the delay; add a cut inner box case (ref chip label); rename the two delegate-session checks. Review A (senior, round 1) on PR #460: https://github.com/jlevy/metabrowser/pull/460#pullrequestreview-5915440680
