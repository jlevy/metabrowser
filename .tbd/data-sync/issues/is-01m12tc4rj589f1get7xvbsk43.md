---
type: is
id: is-01m12tc4rj589f1get7xvbsk43
title: "PR #31 'Known issue' about a stuck commit pane is wrong and must be retracted"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m12tc1tacfnggr44ecjnb17d
created_at: 2026-08-27T23:55:06.897Z
updated_at: 2026-08-28T00:11:18.833Z
closed_at: 2026-08-28T00:11:18.832Z
close_reason: "Retracted in the PR description with the reason: .sr-only uses position:absolute with clip, so it stays in textContent and keeps a non-null offsetParent, and the detection filtered on exactly those. Re-verified with a walker skipping .sr-only and hidden elements: visible pane text empty, spinner present, which is intended."
resolution: null
duplicate_of: null
---
The PR claims the commit detail pane sticks on 'Loading commit…'. That string is screen-reader-only text (git-panel.js renders '<span class="sr-only">Loading commit…</span>' beside a spinner), and .sr-only in styles.css:4230 uses position:absolute with clip, so it stays in textContent and keeps a non-null offsetParent. The detection filtered on offsetParent and textContent, so it read hidden a11y text as visible. Re-verified with a walker that skips .sr-only and display/visibility:hidden: visible pane text is empty and a spinner is present, which is the intended state. Retract the section rather than leaving a false defect attributed to main.
