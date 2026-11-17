---
type: is
id: is-01m7g57pnhtqwqzpgmt41ccc3z
title: "Pulls nav: rows drop branch names; the pull request page keeps them"
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/done/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T17:49:14.288Z
updated_at: 2026-11-17T05:58:37.418Z
started_at: 2026-11-15T17:50:36.254Z
closed_at: 2026-11-15T19:01:56.479Z
close_reason: null
resolution: null
duplicate_of: null
---
The user's request (2026-11-15), verbatim:

"finally the branch names are notneeded in the nav view, it is suficient to have themin themain PR view."

"Together, this should show a lot more text of the PR title. We need a lot more of the text for each PR title in the nav."

Done when Pulls nav rows show no branch names (the pull request page keeps them), the title takes the room, and the Pulls row golden or session, docs/design-system.md, and the Pulls Chrome test say so.

## Notes

Done in 85101438f on claude/pulls-stack-groups (#450): describeRow drops head/base and mergeRefs; the muted line is '#N · author'; the pull request page keeps head -> base. Title room unchanged at the 299 px pane (branches were on the muted line), so the gain came from mb-dzsi and mb-hmv7.
