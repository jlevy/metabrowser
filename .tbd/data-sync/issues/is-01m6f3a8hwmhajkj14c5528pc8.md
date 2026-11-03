---
type: is
id: is-01m6f3a8hwmhajkj14c5528pc8
title: State icons and tokens
kind: task
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m6f3a8zq6770byr49by7dwed
parent_id: is-01m2h7jjgpzyfbf10238j32z6q
hold: null
hold_until: null
created_at: 2026-11-02T21:40:44.731Z
updated_at: 2026-11-03T02:17:38.861Z
started_at: 2026-11-03T00:48:46.739Z
---
Lucide git-pull-request, git-pull-request-draft, git-merge, and git-pull-request-closed in static/icons.js, new color tokens in GitHub's hues for both themes, an accessible name, and the page header's badge using the same icon.

## Notes

2026-11-03, PR 285: Lucide git-pull-request, -draft, git-merge, -closed in static/icons.js (fetched from lucide 1.17.0); --github-pull-open/draft/merged/closed in the plugin stylesheet, GitHub's hues in both themes, held to one hue and 4.5:1 by test_pull_state_colors_keep_their_hue_and_read_on_both_grounds. pull-state.js gives a row and the page's badge the same icon, with the state's name.
