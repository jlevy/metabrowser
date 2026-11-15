---
type: is
id: is-01m7eytdegvzf4k3ntje0zk0c9
title: "Pulls tab: group a native stack's pull requests under a Stack #N toggle"
kind: feature
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-15T06:37:52.961Z
updated_at: 2026-11-15T06:37:52.961Z
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
