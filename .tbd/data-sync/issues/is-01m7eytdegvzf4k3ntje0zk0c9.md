---
type: is
id: is-01m7eytdegvzf4k3ntje0zk0c9
title: "Pulls tab: group a native stack's pull requests under a Stack #N toggle"
kind: feature
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T06:37:52.961Z
updated_at: 2026-11-15T07:41:28.230Z
started_at: 2026-11-15T07:41:28.229Z
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
