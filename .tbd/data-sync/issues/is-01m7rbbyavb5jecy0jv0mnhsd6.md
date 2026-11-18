---
type: is
id: is-01m7rbbyavb5jecy0jv0mnhsd6
title: "View header GitHub toggle: pin it to the header's upper right, and give the active side a clear active color like the app's other toggles (not gray)"
kind: bug
status: in_progress
priority: 2
version: 4
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-18T22:10:20.122Z
updated_at: 2026-11-18T22:55:27.499Z
started_at: 2026-11-18T22:11:59.788Z
---
Owner, 2026-11-18: the toggle between mb and github should be in the upper right, not lower just because the file title is lower on the page. It should also be a consistent color, where the active one is clearer or indicates its activity clearly, like our other toggles, not gray like it is now. (Landed in #552; this refines its placement and states.)

## Notes

Owner, 2026-11-18, follow-up: this toggle should also be present on pull request pages. Related: mb-7t5s (pull requests and commits move onto the view header).

2026-11-18: PR #588 (branch claude/view-header-toggle-states). The toggle sits in the header's corner at a fixed inset and height (--view-header-toggle-inset-top/-inset-end/-height/-width/-room in static/styles.css, documented in docs/design-system.md for the macOS native bar, mb-lxgw), in the shared toggle states (--link on --highlight-bg selected; --muted at rest; --text on --hover-bg hovered). Both segments at every width. Pull request pages draw it through the new SDK helper githubToggle(url), linking the record's html_url. Commit page left alone: its github.com URL would be client-derived and an unpushed commit has none; its header is mb-7t5s's. changelog.d/mb-70d6.md depends on #585 (fragments) landing; until then public_hygiene and test_relative_links_resolve fail on it. For the owner: the PR toggle sits outside the reading column in wide panes; the PR header's View on GitHub link now duplicates it; narrow PR titles give it 66 px.
