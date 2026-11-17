---
type: is
id: is-01m7gzdksz4p3fqcqn9n2aaszh
title: "Diff summary: expands with no scroll bar, indented on the nested rows' step"
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/done/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-16T01:26:50.942Z
updated_at: 2026-11-17T05:59:21.485Z
started_at: 2026-11-16T01:27:42.602Z
closed_at: 2026-11-16T20:03:34.438Z
close_reason: "Merged into main at 1dcbe93 (stack #446 #464-#478) after the gate and the whole-stack review."
resolution: null
duplicate_of: null
---
The user's request (2026-11-15), verbatim:

"We should also drop the scroll bar when it expands and make sure that when it expands, it's indented consistently the correct amount, just like the nested indentations."

Context: the Diff summary (diff-summary.js, diff/styles.css, shared `.changed-file-*` row classes from mb-xlla) expands into a box with its own scroll bar, and its tree's first level does not start on the indentation step its nested levels use.

Done when an expanded Diff summary has no scroll bar of its own and grows in the page's flow, with any bound on its length stated and measured per AGENTS.md "Measure before bounding" and docs/large-content-rendering.md, for example drawing rows on demand rather than an inner scroller. Its tree is indented consistently: the first level sits one indentation step in from the summary's header text, and each nested level adds the same step that nested rows use elsewhere (Files tree and Pulls changed-files tree), measured in Chrome at several depths and pinned in the changed-file rows Chrome test. Keyboard navigation, focus rings, and the collapsed default are unchanged. docs/design-system.md (Diff Summary) and the CHANGELOG say so.
