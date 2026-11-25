---
type: is
id: is-01m89swfr4prd881hdjr4vdwan
title: "Stack page: reorganize to follow the design system (proper summary line, members as a stack like the stack button)"
kind: task
status: in_progress
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-25T16:51:07.641Z
updated_at: 2026-11-25T16:57:52.786Z
started_at: 2026-11-25T16:51:51.705Z
---
User request: 'the stack page should be better organized and follow the design systems we've already established. It's not formatting anything quite the same way. It's got a summary line that doesn't look like a proper summary line. The stack should be formatted in a proper stack, much like the stack button already has.' Audit the stack page against docs/design-system.md (summary lines / Diff Summary, Stacks member row, Pulls row run, change lines with the zero-side rule, chevron convention, tokens) and rebuild it to reuse those components: a real summary line in the established form, and the members listed as a stack in the same member-row form as the PR page's stack button/menu.

## Notes

User, 2026-11-25: the whole stack page must follow the design system completely (full rebuild on established components). Its View on GitHub must target the entire stack and use our shared View on GitHub control style. The stack page also gets its own entry in the Pulls nav column below the stack's members, with a heading of its own.
