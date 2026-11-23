---
type: is
id: is-01m84p4yd4zy6m6qyfvr2a5q74
title: "PR #758 A1: a Pulls-tab file walk replaces the Changes entry with no state, so a reload loses the followed note and the earlier diff the reader chose"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
delegate: claude-code@macbookpro
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
hold: null
hold_until: null
created_at: 2026-11-23T17:09:38.339Z
updated_at: 2026-11-23T17:28:34.309Z
started_at: 2026-11-23T17:20:56.594Z
closed_at: 2026-11-23T17:28:34.307Z
close_reason: "Fixed in 44fb44996 (#758): the page's handle writes its memory in setTab, land and showFile (not a walk's keys) while a diff is mounted, so the entry a walk replaces or a click pushes, each with no state, remembers the note and the reader's choice; github-pull-changes-follow-behavior.js drives the production page host through a walk and a click, and fails at 85001ce. Dispositions: https://github.com/jlevy/metabrowser/pull/758#issuecomment-7108711200"
resolution: null
duplicate_of: null
---
Finding A1 (Medium) of review A on PR #758 (https://github.com/jlevy/metabrowser/pull/758), at head 85001ce25e385c5e518b840d657d95caa648c2ce. Predates the PR: the same probe at merge base 339567248 gives the same result.

A key walk of the Pulls tab's changed files, once it stops, replaces the history entry with a null state: `pull-files-tree.js` `settleWalk` opens with `replace: true`, `static/pull-route.js` `open` calls `replaceHref`, and `static/app.js` `replaceHref` runs `history.replaceState(null, "", href)`. That drops the entry's `pullChanges`. The page writes `pullChanges` only from `mountDiff` (`rememberChanges`). Where the reader chose the earlier diff, the next push is an `offer`, which mounts nothing, so the entry stays empty, and the reload a followed pin makes on a repository URL mounts the record's diff with no offer and no note. A plain reload after a walk drops a followed note the same way.

Probe (github-pull-changes-follow-behavior.js's harness): chosen earlier diff, then `history.replaceState(null)`, address `/pull/7/files/b.py`, `setTab("files")` as the host's `land` does for a jumped route, then a push and a reload. Without the walk the reload draws the earlier diff and offers the newer; after it, the entry's `pullChanges` is null before the reload and the reload draws the newest diff with no offer.

`docs/reviewing-pull-requests.md` ("Staying Current"), as of PR #758, says the line and the choice outlast a reload of the page, with no exception.

Fix (pick one): write the memory again when the host lands the page on a new address of its own (`setTab`, `land` in `pull-page.js`); or write `pullChanges` together with `pullPlace` in `keepPlace`'s write; or have `replaceHref` keep the entry's state when the route stays on the page shown. Add a step to `tests/dom/github-pull-changes-follow-behavior.js` that replaces the entry as a walk does, then reloads after a push.
