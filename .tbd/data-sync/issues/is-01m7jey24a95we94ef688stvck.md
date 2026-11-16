---
type: is
id: is-01m7jey24a95we94ef688stvck
title: "PR header: the Diff summary's place shows the shared pending shimmer while its comparison loads"
kind: feature
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-16T15:17:12.952Z
updated_at: 2026-11-16T20:03:35.249Z
closed_at: 2026-11-16T20:03:35.248Z
close_reason: "Merged into main at 1dcbe93 (stack #446 #464-#478) after the gate and the whole-stack review."
resolution: null
duplicate_of: null
---
Owner, 2026-11-16: "Also, the diff summary takes a little longer to load on a PR view, which is fine. But we should show a progress block with a gray block and the slight color changes (like we do in other parts of the app consistently) when something is still loading."

## Notes

Owner follow-up, 2026-11-16: "Follow a consistent design system for this and a consistent implementation so that the layout doesn't shift, but that component comes in as appropriate." Assigned to layer 25 (claude/pull-header-status) with mb-2u08: shared pending primitive, same box as the summary, no shift on arrival (Chrome check), quiet-period delay, failure clears it, commit page's place the same.
