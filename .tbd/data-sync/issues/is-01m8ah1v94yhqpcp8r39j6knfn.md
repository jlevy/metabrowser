---
type: is
id: is-01m8ah1v94yhqpcp8r39j6knfn
title: Commits tab gets the branch chooser, sharing the Files tab's branch state
kind: feature
status: closed
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-25T23:36:00.547Z
updated_at: 2026-11-26T00:20:08.205Z
started_at: 2026-11-25T23:36:54.774Z
closed_at: 2026-11-26T00:20:08.203Z
close_reason: "PR #857: the Commits tab shares the one revision row and chooser with Files; every Git route reads session_git_location, so both tabs show the served revision."
resolution: null
duplicate_of: null
---
User request 2026-11-25: the nav column's Commits tab needs the same branch chooser the Files tab has (working tree / revision selector), and the two tabs share one branch state: choosing a branch or revision in either shows it in both.
