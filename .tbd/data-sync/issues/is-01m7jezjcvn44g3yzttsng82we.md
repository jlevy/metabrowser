---
type: is
id: is-01m7jezjcvn44g3yzttsng82we
title: "Pull request comparisons are cached and prefetched: a Diff summary seen once never waits again, and likely ones are ready before they are opened"
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-16T15:18:02.388Z
updated_at: 2026-11-16T20:03:36.017Z
closed_at: 2026-11-16T20:03:36.016Z
close_reason: "Merged into main at 1dcbe93 (stack #446 #464-#478) after the gate and the whole-stack review."
resolution: null
duplicate_of: null
---
Owner, 2026-11-16: "Also, we should look at why it isn't being cached. When I browse different diffs, I see a delay repeatedly. It should never delay after the second time because we should have fetched and cached it, and ideally cached it up front, so that the thing comes in faster in the first place."
