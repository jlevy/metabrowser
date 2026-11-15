---
type: is
id: is-01m7ewbhb0sshg0csxn573zwy7
title: "Files tab: a Group by menu as the main control; filters move into the drawer"
kind: feature
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T05:54:48.275Z
updated_at: 2026-11-15T06:11:57.902Z
started_at: 2026-11-15T06:11:57.901Z
---
The user's request (2026-11-15), verbatim:

"let's also add a new drop down entirely: a "group by" menu that is the main menu item. instead of doing a filter, it should gropu by an attribure, and the values would be

"No grouping" (default)
"Age"  [this will be the age groups that are also in the filter menu]
"File type" [ this would group by the overall groups within the file type menu, so "Code", "Documentation", "Data", "Archives", "Media"

but we should reorder both filter and group to put "Documentation" before "Code" all others stay the same.

When this group dropdown is activated, the results of the tree are broken into groups with similar types of headings as we have in the menus. Within each is a full tree of all the items filtered to that value, so in a way, it's a set of filters. All of the filters would then be under the chevron toggle, and only the group by would be the main choice because it's one of the most simple and easy ways to sort files. If you expand it, you would have the three filters that we currently have."

Then: "Let's merge other things first, but then put all of these recent fixes in a new PR on top of the rest." So this ships in one PR with mb-s6vu and mb-1wfn, cut from main after the open PRs merge.

Main today (`renderNavFilterBar` in `static/app.js`):
- The always-visible row holds "Modified within" (recency) and "File type".
- The drawer, behind the chevron, holds "Minimum file size" and "Show ignored".
- "Clear" and the chevron with its active-count badge sit at the row's end.
- The age options (`FILTER_RECENCY_OPTIONS`) are cumulative windows: Live, Past hour, Past day, Past week, Past month.
- The type groups come from `data/file-rollup-format/recommended-file-types.json`, in the order code, docs, data, archives, media, other.

Coordinator's defaults (change one only with a stated reason in the PR):
- **The row:** the always-visible row holds "Group by" alone, with Clear and the chevron. The drawer holds the three filters (Modified within, File type, Minimum file size) plus Show ignored.
- **Values:** "No grouping" is the default and shows today's tree unchanged.
- **Age groups:** these are disjoint bands built from the filter's windows: Live; then Past hour, Past day, Past week and Past month, each holding only what the earlier windows don't; then "Older" for the rest. A Git revision source has no mtime, so it doesn't offer Age, just as it omits the recency filter.
- **File type groups:** these are the taxonomy's groups, with Documentation before Code and the rest in their current order, plus Other last for files in no group.
- **Group order:** groups appear in that order, and a group with no items after the active filters is not shown.
- **Headings:** each group's heading uses the menu group-heading pattern from mb-s6vu, with the group's count. Under it is a full tree of that group's items, after the active filters are applied.
- **Shared order:** Documentation-before-Code is one order shared by the type filter, Group by, and every other surface that lists the groups. Reorder it in one place. If the format treats group order as a published contract rather than presentation, reorder in one shared presentation place and say why.
- **Persistence:** the Group by choice persists exactly as the filter state does, and the keyboard shortcuts that open or badge the filter menus still work after they move into the drawer.

Done when:
- the grouping's data semantics (membership, ordering, counts, and how filters combine with groups) belong to a route or model reached through `metab`, with a nontrivial golden, per AGENTS.md's parity rules;
- the browser's grouping interaction has a browserless session and golden;
- the paint-only parts have a paint-exempt row with its reason and evidence;
- it's measured in headless Chrome on a real folder: the row layout, the drawer, group headings, and a large folder's first paint and expand times against "No grouping" (no spinner under about 50 ms, prefetch by default);
- `docs/design-system.md`, the views/models/routes map and CHANGELOG are updated.
