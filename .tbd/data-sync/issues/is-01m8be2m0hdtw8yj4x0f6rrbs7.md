---
type: is
id: is-01m8be2m0hdtw8yj4x0f6rrbs7
title: In-app route links (a commit, the pull request list, another pull request) open in place on every surface
kind: task
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-26-in-app-link-resolution.md
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7wysdnvzch4gb5zvqwvn04e
hold: null
hold_until: null
created_at: 2026-11-26T08:03:14.577Z
updated_at: 2026-11-26T19:07:56.073Z
started_at: 2026-11-26T19:07:56.073Z
---
From the Fable review of #874 (M2): a /view/ link in rendered text opens in place, but a /commit/<id>, /pulls, or (outside the pull page) /pull/<n> link is a full page load, losing the shell's state. Give the shell one opener for route targets and pass it as enhance's open from every surface (pull-page, stack-page, link-enhancer, git-panel, diff-view).
