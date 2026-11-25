---
type: is
id: is-01m88pf9e36vd3c65ybr0cakhc
title: Recent folders miss folders the user opened, and agents' serves crowd them out
kind: bug
status: closed
priority: 0
version: 4
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/831
    title: Recent targets hold only the user's own opens
    at: 2026-11-25T08:29:50.423Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-25T06:32:15.040Z
updated_at: 2026-11-25T09:00:18.104Z
started_at: 2026-11-25T06:34:36.231Z
closed_at: 2026-11-25T09:00:18.103Z
close_reason: "Merged in #831: the app records every open once; agents' serves no longer record"
resolution: null
duplicate_of: null
---
Reported by the user as a serious bug: a folder they open (seen when it opened as a tab) does not show in the app's recent folders, which must always list the most recently opened folders, most recent first, so that a few folders opened lately are always among the 16 shown. Evidence (2026-11-24): metab --recent --json records every serve of ROOT, and the list holds an agent's verification folder (a worktree's attic/verify-empty) beside the user's own folders, so agents' and tools' serves can push the user's folders out; the app's own defaults also hold a legacy recentFolders array. Done when every way the user opens a folder or repository in the app records it, the app's recent folders show the 16 most recent of the user's own opens most recent first, serves the user did not ask for (agents, tests, tools) never enter the list, and tests pin each part.
