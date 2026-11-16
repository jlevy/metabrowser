---
type: is
id: is-01m7eytdegvzf4k3ntje0zk0c9
title: "Pulls tab: group a native stack's pull requests under a Stack #N toggle"
kind: feature
status: closed
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T06:37:52.961Z
updated_at: 2026-11-16T16:30:49.216Z
started_at: 2026-11-15T07:41:28.229Z
closed_at: 2026-11-16T16:30:49.213Z
close_reason: "Merged into main at afda3599f (stack #446 lower layers)."
resolution: null
duplicate_of: null
---
The user's request (2026-11-15), verbatim: "Feature is that within the Pulls tab, there is an option to group all PRs in a stack in a recursive toggle for the stack itself, so that if there are say 4 PRs in the stack, the stack itself (which github gives a number) woudl be somethig like Stack #1234  and then it would be pre-opened but include all PRs in that stack."

On main, `builtin_plugins/github/pull-stacks.js` indexes native stacks (`createStackIndex`) by pull request number. A pull request can belong to more than one stack. The Pulls rows show a stack position badge such as "2/4" (`paintStackBadge` in `pulls-panel.js`). Stack metadata is optional, and core pull request data never waits for it.

Design and defaults: see the plan spec, section "Pull Stack Groups". In short:
- an option in the Pulls toolbar groups the list by stack, and the choice persists;
- each stack with members in the list gets a "Stack #N" row with its pull request count, open by default;
- the stack's pull requests sit under it in stack order, each keeping its own changed-files toggle;
- pull requests in no stack follow the stacks;
- a pull request in two stacks appears once, under the first, and its badge names the others;
- with missing or stale stack data the list stays flat and the option says why;
- stack rows are tree rows for the Pulls keys.

Done when grouping, ordering and membership live in the browserless Pulls model with a session and golden; the paint has its paint-exempt evidence; it's measured in headless Chrome with a real stack; and CHANGELOG, `docs/design-system.md` and the views/models/routes map are updated. Pull request 5 of the plan's stack.

## Notes

Added requirement (user, 2026-11-15), verbatim: "On the toggleable grouping for stacked PRs in the Pulls tab, we should make sure that we use the same design system consistently for labeling stacks as we do in the button that's on the stack that has a drop-down menu. Make sure that the design system is fully consistent and clean in terms of the links to the hovers and the header text on the stack, which will be gray and all caps. Like it is in the toggle menu currently, but also in the nav grouping make sure that this design system is cleanly documented and applied consistently for stacks."

What the PR page's stack control is on main (`builtin_plugins/github/pull-page.js`, around lines 3120-3200):
- A `summary.btn.github-pull-stack-trigger` shows the layers icon and the position ("2/4").
- Its `.menu.github-pull-stack-menu` opens with `.menu-section-label` "Stack #N", in the label register (gray, uppercase, tracked).
- Then come member rows, `a.menu-item.github-pull-stack-member`, top of the stack first. Each holds a title, a position and a #number, and the current pull request has `aria-current="page"`.
- The Pulls rows carry the same position badge (`paintStackBadge` in `pulls-panel.js`).

Added to Done when:
- **One stack design,** stated once in `docs/design-system.md` (a "Stacks" section) and used by both the PR page's stack menu and the Pulls tab's stack groups. It covers:
  - the "Stack #N" label: gray, all caps and tracked, in the same label register as the stack menu's heading, at the inset mb-s6vu sets for menu group headings;
  - the position badge with its icon;
  - member rows: title, position, #number, and the current-pull mark;
  - member order: the same order the stack menu uses;
  - links and their hover and focus states;
  - the hover tip text.
- **The Pulls stack group row** uses that label for its header text. Its hover, focus and link behaviour match the member rows' wherever the two do the same thing.
- **Anything that labels a stack its own way** (the menu, the badge tip, the group row) moves onto the shared classes and tokens, with no per-surface copies.
- **A test** pins that the stack menu's heading and the group row's header resolve to the same label tokens, and that member order matches the stack menu's.

Built (2026-11-15, sub-agent, branch claude/pulls-stack-groups, local only, not pushed): commits 6ced50c7 (merge of claude/menu-group-pattern, since claude/diff-summary did not hold pull request 1's .group-heading; a restack onto PR 1 makes it empty), 16d8f32d (feat), 4404e1ad (docs).
- Model: pull-stacks.js groupByStack, stackLabel/stackPosition/stackPositionHint/stackMenuOrder, stackCaption(..., under); pulls-panel.js describeStackGrouping and the controller's grouping (setStacks, setGroupByStack, setStackOpen, enterStack, leaveToStack). Stacks ordered by their first listed member; shared member once under the first, badge names the other ("4/4 · #300 2/2", also in flat mode); stack with no unplaced members gets no row; stale-but-retained snapshot still groups (consistent with badges and the menu); identity mismatch, absent, gh_stack_missing, or no listed member in a stack keep it flat with the reason in the chip's tip and aria-description.
- UI: .chip.chip-toggle "Group by stack" (Layers glyph, --chip-height, numbered 4 before Reload 5), on by default, choice in mb.prefs github.pulls.groupByStack. Stack row: div treeitem, .group-heading.github-pull-stack-label, count where the age is; members aria-level 2 and one --tree-indent in (files follow). Keys: J/K stop on stack rows, Enter/Space toggle, Right open/enter, Left close/leave to stack.
- Stack menu: heading .group-heading.github-pull-stack-label, members via stackMenuOrder, trigger data-tip-text; member position ink was link blue by inheritance, now --text.
- Tests (each red on the pre-change source): tests/dom/github-pulls-stack-groups-session.js + golden cli-ui-github-pulls-stack-groups.tryscript.md; tests/test_github_pulls_stacks_chrome.py (+ tests/dom/github-pulls-stacks-chrome.mjs, live server, fake gh stack with #286 [7..10] and #300 [5,10]); tests/test_github_stack_design.py; updated github-pull-stacks-behavior.js, panel session number story, pulls-nav golden copy, keymap/vocabulary/process-group registries; stack fixture gained a recorded "shared" answer.
- Measured (headless Chrome, 1280x900, load 8-19): first Pulls row 964-1094 ms after vs 1006-1013 ms before (one before outlier 2199 ms); stacks grouped 1068-1186 ms after the tab press; toggle 8-36 ms. Label tokens identical on both headers; stack row 24 px; member inset +16 px.
- Local: make -o install lint-check passed; cli-ui goldens 74 passed; focused pytest set passed incl. Chrome. Not run: full make test / make verify, macOS app, light theme screenshots.

PR #450 (draft, 2026-11-15): https://github.com/jlevy/metabrowser/pull/450, base claude/diff-summary (#448). The merge 6ced50c7 was dropped: the two commits were rebased once onto the restacked claude/diff-summary (7ca39485, which holds PR 1 through #444, #445, #447), now 6bb61ee2 (feat) and c7e8573e (docs); head c7e8573eac6e66aea96e4068d0e336c760244082. Conflicts in docs/e2e-testing.md and tests/test_process_group.py (the Chrome test lists, both sides kept, with test_prose_faces_chrome) and CHANGELOG (both kept). Linked with gh stack link into native stack #446: [444, 445, 447, 448, 450]. After the rebase: lint-check, parity, 75 cli-ui goldens, the stack-groups session, and 135 focused pytest tests (incl. the stack Chrome test and header Chrome launch/pulls/header-wide) passed locally; pushed with --no-verify. CI run 43695631545: all 9 checks passed (lint, distribution, stack-integration, test 3.12/3.13/3.14/3.14t, admitted-git 2.43.7/2.50.1). Not merged, not marked ready. Stale handling confirmed by the coordinator: missing stacks or another account's keep the list flat; a kept snapshot still groups.

Review A on #450 (2026-11-15, changes requested: A1 High, A2-A6 Medium, A7-A8 Low, A9-A11 suggestions): all addressed in 790ffa64 per the coordinator's decisions (A1 regroup keeps the top in view, A2 count every listed member with "N under Stack #M", A3 read-ahead in drawn order, A4 toggleHtml worded chip "Stacks" named "Group by stack", A5 mounted-panel session + nav Space story + Chrome Space/press/member files, A6 numbering records, A7 remedies, A8 docs, A9 font, A10 one SVG parse, A11 Layers glyph names another stack). Dispositions: https://github.com/jlevy/metabrowser/pull/450#issuecomment-6892524143. Toolbar fit at the default 299 px pane: 36 px overflow with "Stacks" (old glyph chip 11 px, icon-btn 7 px, 23 px spare with no chip); recorded, not asserted. Then merged origin/claude/diff-summary (92f49af5) as 9d6c6f1b (conflicts in pull-page.js stack menu naming, design-system numbering table, Chrome registries; github-pull-stack-mount-behavior.js updated for the label class). Locally after the merge: lint-check, 75 cli-ui goldens (incl. the panel golden after the fix), sessions, and 136 focused pytest tests incl. Chrome passed. CI on 9d6c6f1b was still pending at handback.
