---
type: is
id: is-01m8a4nktj57nytxbengdmfd67
title: "Guide pull request rows read in the member order: title, place, number, author"
kind: task
status: in_progress
priority: 1
version: 2
spec_path: docs/project/research/research-2026-11-22-annotated-collections-and-guided-pr.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m8806zrnxn9jwj89hffd2yv7
hold: null
hold_until: null
created_at: 2026-11-25T19:59:36.785Z
updated_at: 2026-11-25T19:59:40.092Z
started_at: 2026-11-25T19:59:40.091Z
---
A guided review's {pull} reference row follows the design-system rule PR #843 added (docs/design-system.md, Stacks: 'A stack's member reads in one order wherever it appears: its title, its place, its number, and its author'). Today the row draws the number first, then the title, then 'Stack #N k/m'. Redraw it as the stack menu and the stack page's members list draw a member: title, place, number, author, reusing their classes and markup (a shared helper if none exists). The guide target's author fields keep the stacks route's shape (author, avatar). Also check that the guide's {commit} row's age ends the row (docs/design-system.md, 'Ages End the Row'). Stacked on #847 (native stack 846).
