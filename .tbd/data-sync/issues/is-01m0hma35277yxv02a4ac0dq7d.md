---
type: is
id: is-01m0hma35277yxv02a4ac0dq7d
title: A filtered tree has no row for the folder you are standing in
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m0hhjf2e1w8tp30ay4tj8183
created_at: 2026-08-21T07:42:02.913Z
updated_at: 2026-08-21T07:42:02.913Z
---
A filter can exclude the folder the reader is currently in. Open a folder from a breadcrumb, a link, or a pasted URL while a filter is on, and if that folder holds no match the nav panel has nothing selected: the main pane shows the folder, the tree does not contain it.

This is no longer the vanishing-row bug — a row never disappears as a result of the click that opened it, because /api/tree prunes before the row is drawn. What is left is the case where the selection and the filter genuinely disagree, and today the filter wins silently.

Options worth weighing before building anything:

- Pin the selected path and its ancestors into the filtered tree, marked as present-because-selected rather than present-because-matching.
- Say it instead of showing it: a line in the panel reading that the open folder is outside the current filter.
- Leave it, on the grounds that a filter is a question and the answer legitimately excludes where you happen to be standing.

Lower severity than the beads under this epic that are fixed: reaching it takes navigating to an excluded folder by some route other than the tree itself.
