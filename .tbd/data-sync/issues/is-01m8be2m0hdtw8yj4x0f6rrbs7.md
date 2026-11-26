---
type: is
id: is-01m8be2m0hdtw8yj4x0f6rrbs7
title: In-app route links (a commit, the pull request list, another pull request) open in place on every surface
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-26-in-app-link-resolution.md
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7wysdnvzch4gb5zvqwvn04e
hold: null
hold_until: null
created_at: 2026-11-26T08:03:14.577Z
updated_at: 2026-11-26T21:33:21.454Z
started_at: 2026-11-26T19:07:56.073Z
closed_at: 2026-11-26T21:33:21.454Z
close_reason: Implemented in https://github.com/jlevy/metabrowser/pull/891 (CI green at d9463651; senior review G1-G4 fixed).
resolution: null
duplicate_of: null
---
From the Fable review of #874 (M2): a /view/ link in rendered text opens in place, but a /commit/<id>, /pulls, or (outside the pull page) /pull/<n> link is a full page load, losing the shell's state. Give the shell one opener for route targets and pass it as enhance's open from every surface (pull-page, stack-page, link-enhancer, git-panel, diff-view).

## Notes

PR: https://github.com/jlevy/metabrowser/pull/891
