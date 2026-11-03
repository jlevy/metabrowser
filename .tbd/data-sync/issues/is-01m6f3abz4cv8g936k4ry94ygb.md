---
type: is
id: is-01m6f3abz4cv8g936k4ry94ygb
title: The tab and page on a checkout
kind: task
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m6f3aces3z20vehpwkkxdd7m
parent_id: is-01m2nz9gwd4wyxmrpx49cp9yck
hold: null
hold_until: null
created_at: 2026-11-02T21:40:48.227Z
updated_at: 2026-11-03T07:15:47.565Z
started_at: 2026-11-03T07:01:13.676Z
---
Tab from context, including a subdirectory, the network only while the tab is the visible panel, no Browse code, a note when HEAD is the pull request's head, and the fork wording.

## Notes

2026-11-03 HANDOFF: on wip/pulls-5-checkout (24a95778). Done: server.py draws the tab wherever a repository context exists, so a checkout and its subdirectory get it (tests/test_pulls_nav.py). pulls-nav.js takes a checkout dep: no prefetch, refreshAhead false, a mount on show only, and a stop on hide (pulls-nav session story). pulls-panel shows the visible origin line, which is the fork wording, and its own not-listable text (panel session). pull-page has no Browse code, a checkoutAtHead note with a root link, and the no_store Files changed text (page session part 2). Not done: a real-Chrome check in both themes; the checkout page load measured against the base (within 1.1x). See mb-cbak.
