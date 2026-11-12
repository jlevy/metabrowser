---
type: is
id: is-01m78aeq9jvzfhbxstf4zp3haa
title: "PR #375 A7: stack #376 conflicts with main in CHANGELOG.md"
kind: bug
status: closed
priority: 2
version: 4
delegate: claude-code@spud10
labels:
  - stack-376
dependencies: []
parent_id: is-01m78ae0p02ghts4vw9h2vrmhp
hold: null
hold_until: null
created_at: 2026-11-12T16:46:31.729Z
updated_at: 2026-11-12T23:26:16.431Z
started_at: 2026-11-12T16:46:42.835Z
closed_at: 2026-11-12T23:26:16.430Z
close_reason: "Resolved by the end-of-stack rebase of #376 onto main 27ea216c: each layer's CHANGELOG entries now sit after main's Unreleased entries, and all six PRs report MERGEABLE (#374 head 0de9cd56)."
resolution: null
duplicate_of: null
---
Medium, stack-level, owned by #374. PR #375 review A (https://github.com/jlevy/metabrowser/pull/375#pullrequestreview-5871448143). git merge-tree --write-tree origin/main against d941c229 and 8154909 reports CONFLICT (content) in CHANGELOG.md: main 02db045a added a File Overview entry at the top of ## Unreleased (96d85c05, 1d3d3401). stack-integration fails on #374 and #375. Deferred to the one end-of-stack rebase of stack #376 onto main once every layer is done (the user's choice): rebase #374 onto main keeping both CHANGELOG entries, then gh stack rebase --upstack and resolve this layer's hunk the same way.

## Notes

Deferred in the review A disposition reply on PR #375. Waits on the single end-of-stack rebase of stack #376 onto main once every layer is done (the user's choice); #374 owns the conflict. At that rebase: keep both CHANGELOG.md Unreleased entries on #374 (main's File Overview entry from 96d85c05 and 1d3d3401, and the stack's), then gh stack rebase --upstack and resolve #375's hunk the same way. Close when stack-integration passes on #375.
