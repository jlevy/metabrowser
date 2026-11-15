---
type: is
id: is-01m7gd9yc4wfxwvtgetdh86bwa
title: "Group by: a choice shows at once and the tree shows it is regrouping, even when slow"
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T20:10:16.323Z
updated_at: 2026-11-15T20:11:19.441Z
started_at: 2026-11-15T20:11:19.440Z
---
The user's report (2026-11-15), verbatim:

"It seems like choosing the grouping options has regressed and does nothing. When I select by file type or by age in the files view, it doesn't change currently."

Coordinator's diagnosis, measured against the running app (stack top b3fcd2508), served folder /Users/levy/wrk/aisw/trading/ with more than 200,000 files:
- Choosing a grouping does work, but `/api/tree?group_by=type&depth=2` takes 4.5–5.6 s warm and 8–9 s cold, against 5 ms for the ungrouped tree. Other folders take 20–150 ms.
- During the wait the old tree stays and the only feedback is the trigger's breathing. The first time I chose "By file type" right after opening the menu, while the menu-open prefetch of both groupings was in flight, the filter state became "type" but the trigger still read "No grouping" 1.5 s later and no sections had appeared. On a second try the trigger updated at once. The grouping arrived after about 9 s either way.

So to a reader the choice looks like it did nothing. mb-navs covers the server's speed; this bead covers the feedback.

Done when:
- A choice in Group by shows at once, in the same frame, whatever the server takes. The trigger reads the chosen value immediately, including when it is chosen while the menu-open prefetch is in flight.
- After `--loading-state-delay`, the tree shows plainly that it is regrouping, by a documented loading treatment from the design system (for example the tree dimmed under a "Grouping by file type…" status in the nav metadata line), not only the trigger's breathing.
- Choosing another value, or No grouping, during a slow load cancels the stale one.
- Covered by the Group by browserless session (the decisions) and the Files Chrome test, with a server delay injected to make the load slow.
- Stated in docs/design-system.md "Grouping the Files Tree" (Waiting).
