---
type: is
id: is-01m6f3a8hwmhajkj14c5528pc8
title: State icons and tokens
kind: task
status: closed
priority: 1
version: 6
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
updated_at: 2026-11-04T17:14:29.891Z
started_at: 2026-11-03T00:48:46.739Z
closed_at: 2026-11-04T17:14:29.891Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Lucide git-pull-request, git-pull-request-draft, git-merge, and git-pull-request-closed in static/icons.js, new color tokens in GitHub's hues for both themes, an accessible name, and the page header's badge using the same icon.

## Notes

2026-11-03, PR 285: Lucide git-pull-request, -draft, git-merge, -closed in static/icons.js (fetched from lucide 1.17.0); --github-pull-open/draft/merged/closed in the plugin stylesheet, GitHub's hues in both themes, held to one hue and 4.5:1 by test_pull_state_colors_keep_their_hue_and_read_on_both_grounds. pull-state.js gives a row and the page's badge the same icon, with the state's name.

2026-11-03 (PR #285 addressing, B1): the four glyphs moved from static/icons.js to builtin_plugins/github/pull-state.js: -251 compressed bytes from every folder's startup scripts, +445 to the plugin; first row at /pulls unchanged over 9 pairs (median ratio 0.998).
