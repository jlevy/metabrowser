---
type: is
id: is-01m7gasjz3qnvc0v9dzsrt2w2p
title: Tooltips only when they add information; none on Pulls nav rows
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-15T19:26:23.202Z
updated_at: 2026-11-15T19:26:23.202Z
---
The user's request (2026-11-15), verbatim:

"Also, one more small item on the nav column the PRs should not have tooltips. It's distracting. Our general principle should be that you don't have a tooltip unless it adds substantive new information."

Done when:
- Pulls nav rows (pull request rows, stack rows, and their parts) show no tooltip.
- docs/design-system.md states the principle once: a control or row gets a tooltip only when the tooltip adds substantive information that is not already visible, such as a glyph-only control's name, an exact time behind a relative age, or the full text of something cut short. A tooltip that repeats visible text is removed.
- The app's other tooltips are audited against that rule (data-tip-text, title, and the shared tip machinery). Each one that only repeats visible text is removed. Each kept one has its reason recorded, and borderline ones are listed for the user rather than decided silently.
- Ideally, a check in tests/test_design_vocabulary.py (or the tip machinery's own tests) keeps a tip from equalling its element's visible text.
- Chrome or browserless checks pin that Pulls rows have no tip. The CHANGELOG says so.
