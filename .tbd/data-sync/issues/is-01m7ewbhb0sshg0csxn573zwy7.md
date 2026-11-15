---
type: is
id: is-01m7ewbhb0sshg0csxn573zwy7
title: "Files tab: a Group by menu as the main control; filters move into the drawer"
kind: feature
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T05:54:48.275Z
updated_at: 2026-11-15T08:11:50.461Z
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

## Notes

PR #445 (draft, base claude/menu-group-pattern = PR #444), branch claude/menu-groups-height, head addd1a62; second in native stack #446. Commit d94c119f (Group by), then the merge of PR 1.

Change: Group by (No grouping, Age, File type) is the Files filter row's one control; Modified within, File type, Minimum file size, and Show ignored move into the drawer (badge counts filters; Clear keeps the grouping). Sections: one per nonempty group, headed with the menu group pattern (.group-heading at the tree's 12 px inset, file count, names its section and tree), each a full tree of the group's files after the filters; a folder opened in a section lists only its group. Age bands: Live, Past hour, Past day, Past week, Past month (disjoint), Older; a recency filter intersects them; no Age on a Git pin. Type groups: Documentation, Code, Data, Archives, Media, Other (registry classification, unrecognized files in Other). One presentation order FILE_TYPE_GROUP_DISPLAY_ORDER (file_type_filters.py) shared by the type filter, Group by, and File Overview (fileTypes.displayGroups); the registry keeps the File Rollup Format's fingerprinted order. Keys: Group by is 1, the drawer's filters follow while it is open (a closed drawer is inert). Opening the menu prefetches both groupings; the trigger breathes while they load; file changes refresh sections, paced as the tally is.

Route: /api/tree?group_by=type|age (groups in order with files, size, entries, tree) and ?group=<by>:<id> (one group's tree); model metabrowser/tree_groups.py; provider InventoryFilter.type_group and older_than_seconds; type groups on Git pins.

Tests: goldens cli-api-tree-groups (data row navigation.group-by-membership) and cli-ui-files-group-by with tests/dom/files-group-by-session.js (interaction row navigation.group-by-sections), test_tree_groups.py, test_tree_groups_session.py, the Group by part of test_files_tab_chrome.py (paint-exempt row navigation.group-by-sections-paint), plus updated sessions and goldens for the row, numbering, and Documentation-first order.

Measured (headless Chrome, 2026-11-15): 22,104 files: /api/tree 34 ms, group_by=type 106 ms, age 58 ms; choosing File type to painted 114-163 ms; opening a folder 30-32 ms grouped or not, no spinner. 100,000 files: /api/tree 121-194 ms, type 724-909 ms, age 490-515 ms; choosing File type 1,062-1,137 ms (662-828 ms after 400 ms on the open menu, prefetch); No grouping 78-158 ms; opening a folder 24-32 ms, no spinner. Follow-up: a single-pass provider grouping would bring File type near the ungrouped cost.

Local: full pytest (6,232 passed; the 14 failures were stale source-shape tests and goldens, fixed and rerun), all 433 goldens, lint-check, parity. CI on PR #445 (run 43691800719): all nine checks passed (lint, distribution, stack-integration, admitted-git 2.43.7 and 2.50.1, test 3.12, 3.13, 3.14, 3.14t). Bead left open until the PR merges.
