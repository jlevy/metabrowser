---
type: is
id: is-01m88eccxtthhtehhz0g0czp33
title: A Pulls stack's file row is replaced while test_github_pulls_stacks_chrome waits for its tooltip
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
created_at: 2026-11-25T04:10:51.622Z
updated_at: 2026-11-25T04:10:51.622Z
---
Seen once locally while building PR #821 (mb-vkhd/mb-85op/mb-lqkb), at load average about 360-475. tests/test_github_pulls_stacks_chrome.py failed the check 'a top-level changed file's row shows no tooltip while its name is whole': fileTips.whole.kept was false, so README.md's file row element under #106 was replaced during the tooltip wait. It passed one plain rerun, four reruns with a MutationObserver logging removals, three later runs, and CI, so the replacement was not caught in the act.
Candidate mechanisms to confirm or rule out: a scroll-triggered repaint in pull-files-view.js paintWindow, or a list repaint after the fixture's background pull-refresh landing during the wait. Done when the mechanism is named from evidence and either the repaint keeps the row element (if replacing it is a bug a user would see as a lost hover) or the test waits on the condition that makes the row stable.
