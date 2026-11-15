---
type: is
id: is-01m7eyedp8mvkq8mgd3937dxqw
title: "Diff summary: one collapsible changed-files tree with folder roll-ups, replacing the diff toolbar's count line"
kind: feature
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-15T06:31:20.007Z
updated_at: 2026-11-15T06:31:20.007Z
---
The user's request (2026-11-15), verbatim:

"one more item, we should consolidate to have a proper concept of a "Diff summary" that shows the same information you see within the toggle of a PR diff, i.e. each folder organized by toggles,

a diff sumary should be collapsible and better tally at each folder level of lines added/removed rolled up if the fodler is closed.

at the top it sholuld have a summary more like "35 changed files (2 added, 3 removed, 30 modified)  +1234 -3423" or similar, following our standard conventions

note this should replace the more minimal "41 changed files
+6526
−555" currently at the top of a PR rendering. And it basically should reuse the same design systems we use in the nav panel, but adapted to the view there.

It also should collapse by default."

On main:
- **The line being replaced:** `renderDiffToolbar` in `builtin_plugins/diff/diff-view.js` (around line 1357) draws "N changed files +A −D" (`.diff-summary`, plus "(estimated)" when the totals aren't exact) for any multi-file diff: a pull request's Changes, the Git commit view, and a diff file.
- **The tree the user means** ("the toggle of a PR diff") is the Pulls tab's per-PR changed-files tree:
  - `builtin_plugins/github/pull-files-tree.js` is the logic without a DOM: `buildFileTree`, `visibleRows`, `initialExpansion` and `describeFileList`, run by `tests/dom/github-pull-files-tree-session.js` with a golden.
  - `pull-files-view.js` is the paint. Its file rows show a status badge plus `+A −D`. Its folder rows show only a chevron and a name.
  - It is fed by the `pull-files` route.

Coordinator's defaults (change one only with a stated reason in the PR):
- **One concept, one model:** "Diff summary" is a diff-plugin component, used wherever a multi-file diff shows its totals: PR Changes, the Git commit view, and diff files. It is built on the same tree model as the Pulls tab, moved or shared rather than copied, and the Pulls tab's tree gains the same folder roll-ups.
- **The header line:** "35 changed files (2 added, 3 removed, 30 modified)  +1,234 −3,423".
  - The breakdown lists only non-zero statuses, in a fixed order (added, removed, modified, renamed, then any other status the list carries).
  - Counts use the shell's number formatting, and the line counts use the existing `diff-stat-add` and `diff-stat-del` tokens and the U+2212 minus.
  - "(estimated)" stays when the totals aren't exact.
  - The header is the disclosure toggle, and the summary is collapsed by default.
- **Open:**
  - The tree shows the same rows as the Pulls tab: folders as toggles, single-child folder chains drawn as one row, and files with their status badge and `+A −D`.
  - A folder row shows its rolled-up `+A −D` while it is closed. Whether it also shows them while open is your call, but stay consistent with the Files tab's folder tallies.
  - Activating a file row jumps the diff to that file, as the Pulls tab's tree does.
  - The design is the nav panel's tree rows, chevrons and tallies, adapted to the page.
- **States:** large lists and unknown line counts (`null`) behave as the Pulls tab's do. The tree is lazy (nothing mounted until it's opened), has a disposal path, and is windowed for long lists if the Pulls tab's is.

Done when:
- roll-ups, the status breakdown and the header text belong to the browserless model, with a session and golden; any new data belongs to a route reached through `metab` with a golden, per AGENTS.md's parity rules;
- the paint has a paint-exempt row with its evidence;
- it's measured in headless Chrome on a large real pull request (closed and opened, first paint, and open time);
- the old line is gone everywhere it was replaced;
- `docs/design-system.md`, the views/models/routes map and CHANGELOG are updated.

Ships in the combined PR with the other recent items (mb-s6vu, mb-1wfn, mb-sogv, mb-m5dd).
