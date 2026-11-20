---
type: is
id: is-01m7h20ams5tqrenravhhqc7z3
title: "PR #449 A10: decide whether commit comparisons honor textconv at all (user decision)"
kind: bug
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-16T02:12:01.304Z
updated_at: 2026-11-20T17:24:05.171Z
---
Deferred from review A of PR #449 (A10, https://github.com/jlevy/metabrowser/pull/449#pullrequestreview-5913959566). Waits on the user's decision: should commit comparisons honor textconv drivers at all? The project's research (docs/project/research/research-2026-08-26-git-status-and-dirty-working-trees.md:234, research-2026-07-17-web-diff-viewer-architecture.md:531) and the working-tree diff plan (docs/project/specs/active/plan-2026-08-26-git-status-and-working-tree-diffs.md:797) point to --no-textconv. Passing --no-textconv on every patch run would make H116's one run unconditional and remove src/metabrowser/diff/adapters/textconv.py, the first comparison's git var and git config, the Git-before-2.42 path, and the 3-process case, but it changes the answers for folders that configure a driver, which is outside H116's byte-identical scope.

## Notes

Disposition on PR #449: deferred, waiting on the user's decision.
