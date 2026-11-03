---
type: is
id: is-01m6f39zpnk9rc3kjy552b88qj
title: "Step 4: changed files in a row, expandable like a folder"
kind: feature
status: in_progress
priority: 1
version: 13
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m2nz9gwd4wyxmrpx49cp9yck
parent_id: is-01m6f39t9zax1nbajkkasya6st
child_order_hints:
  - is-01m6f3a9djmnfvp42fmnwhwtr7
  - is-01m6f3a9tmf2t5m4pcb97gfr0j
  - is-01m6f3aa89emxbf0rwesa8gt7x
  - is-01m6f3aapq93hetda33rkdc9zv
  - is-01m6f3dkmagq7az0j52zq4je42
hold: null
hold_until: null
created_at: 2026-11-02T21:40:35.668Z
updated_at: 2026-11-03T07:19:02.636Z
started_at: 2026-11-03T06:46:31.128Z
---
Delivery step 4, added 2026-11-02. A row is a container: it expands to its changed files as a tree using the Files tree's row contract, from one gh request per 100 files with no Git. File rows open /pull/<n>/files/<path>. See the plan's Changed Files in a Row.

## Notes

2026-11-03 HANDOFF (second half, paused mid-work). Branch wip/pulls-4-files at fff7d6a3, cut from claude/pulls-4-files c2059f4e. Nothing was pushed to claude/pulls-4-files; #287 untouched.

DONE AND TESTED (2cd41853, 02dd2d04): /pull/<n>/files/<path> end to end except the tree. Server: view_routes.PullRoute, decode_safe_pull_route and format_pull_href take a file path (segment by segment, shape-checked, never on disk); pull_shell serves it. --show /pull/<n>/files/<path> adds `file=<display> file_list=<state> listed=<status|no> complete=` from the pull-files route (new section in cli-github-pull-files.tryscript.md). Client: pull-route.js parsePull returns file, pullHref(number, tab, file), pullHistoryAction carries file; the host lands a file route on the page's showFile (after mount, since app.js's mount drops route.file, or in place); a `jumped` open moves only the address; attachedHost()/pageFor(number) hand the shell's host to the Pulls tab with no app.js change. Page: pull-page.js showFile(path) (switches to Files changed in place, jumps once the diff mounts, newest wins, a saved place wins) and onPageRoute; scrollToFile no longer throws on a failed diff. Tests: test_pull_page_route grammar and refusals; _SHELL_ROUTES has /pull/7/files/src/app.py (plain folder loads nothing new, passes); navigation-route-behavior and page second session, goldens regenerated. Docs: architecture.md URL grammar; arch map kind, route and parity rows.

HALF DONE (fff7d6a3, wip: tsc and Biome clean, the glue has NEVER RUN in a browser): pull-files-tree.js createFileTreeController, createRowExpansion, describeFileTree and fileListFailure (file-list words), windowRange, and position/setSize/display on visibleRows. New pull-files-view.js: a windowed flat tree in .tree-children[role=group] owned by the row (aria-owns), rows positioned by index, the anchor always drawn, no .tree-item and no data-tree-id. pulls-panel.js: chevron column, aria-expanded, click opens and toggles, the shown page's row auto-expands and closes again when the page moves on unless a reader opened it, handle gains expand/collapse/moveFile/fileLeft/fileRight/activateFile and setCurrent(number, file). pulls-nav.js: Right/Left on rows, a pull-files key scope (Up/K, Down/J, Left, Right, Enter/Space). styles.css rules.

NEXT, IN ORDER: (1) run it in real Chrome over CDP and fix what breaks; (2) measure and set AUTO_EXPAND_FILES (placeholder 300, pulls-panel.js) and FILE_ROWS_OVERSCAN (placeholder 40, pull-files-view.js); (3) the walking budgets; (4) browserless coverage of the new controller, expansion and windowRange in github-pull-files-tree-session.js, the new keys in pulls-nav-session.js, parity rows, register file rows in test_nav_like_row_sets_share_the_vertical_keyboard_contract, test_row_text_shares_one_baseline, test_inline_change_stats_are_bold, design-system lines, a paint-exempt row for pull-files-view.js; (5) arch-nav-containers.md Collection panels wording (not done), CHANGELOG; (6) mb-egnj, mb-w5rc; (7) make lint-check and make test, then push to claude/pulls-4-files.

DECISIONS TO CONFIRM: "narrowed to that file as a patch's child is" is built as Files changed of the whole comparison with the diff jumped to that file (scrollToFile pins it at the top), not a one-file document: a key walk moves the address at each stop, and a narrowed document per step would fetch the comparison again per step and drop the jump contract. "The selection follows a reader who scrolls the diff by hand" is not done: the diff view has no accessor for the file at the top, so it needs one from its owner.

MEASUREMENTS: none in a browser. Large pull requests the list can reach (newest ~1,000, its cap), from a read-only GraphQL search: astral-sh/ruff#29817 (1,031 files) and #29121 (1,627); python/typeshed#16357 and #16162 (5,855); django/django#21915 (886) and #21728 (2,235). django/django#15387 (2,003) is past the list's cap, so its row cannot be reached from the list.

SURPRISING: Safari limits replaceState, so a held key must not replace per step: the diff jumps per key and the address moves when the walk stops (FILE_WALK_SETTLE_MS). The tree keyboard module can't be reused for these rows: it registers fixed ids in the "tree" scope and rewrites every row's tabindex per move.

2026-11-03 status: branch claude/pulls-4-files, head c2059f4e (overlay work merged in). Data half done at a84968ab (mb-ywt7, mb-cl42; make test green): PullFileList from the local comparison or GitHub's list, read progressively, routes pull-files and pull-files-refresh, the browserless tree model. Second half in progress: rendering under each row (mb-jagq), /pull/<n>/files/<path> (mb-e8cs), the keyboard jump through scrollToFile (mb-zx9q), the diff accessor (mb-w5rc), changed_files on the record (mb-egnj).

2026-11-02: the performance study has reported (exp-040 on origin/claude/v012-pr-review-perf). The gate on the tree's shape and keyboard is lifted; jump-scrolling waits for the scrollToFile contract (mb-zx9q). Binding: build the tree from a file list and never from hydrated documents. The plan's gh pulls/<n>/files list satisfies this and needs no Git. A windowed list is likely needed past a few hundred files, and the tree must be bounded or virtualized at 1,183 rows.

2026-11-02: GATE. Do not fix this step's data shape before the large-pull-request performance study on branch claude/v012-pr-review-perf reports; the other session will message its result. It may recommend splitting the manifest from the patches, virtualizing, and a changed-files list, which overlaps this tree. MAX_HYDRATED_FILES and MAX_MANIFEST_FILES bear on it. Stress case: 1,183 files, +281,131 lines.
