---
type: is
id: is-01m7v8bs62dz0nqmqb9rnhgsdb
title: "Branches follow the repository: a view of a branch tracks it in mirror and folder modes; a commit or the working tree stays put"
kind: epic
status: in_progress
priority: 1
version: 6
delegate: claude-code@spud10.local
labels: []
dependencies: []
child_order_hints:
  - is-01m7v8ctk4af96q7ykmb5psdd7
  - is-01m7v8cv4e6sjryervx72qmn90
  - is-01m7v8cvnhxhpd84rsjmtqqrm3
  - is-01m7v8d2dzrf8cg3wrxezg9bh1
hold: null
hold_until: null
created_at: 2026-11-20T01:15:32.417Z
updated_at: 2026-11-20T01:17:55.716Z
started_at: 2026-11-20T01:17:55.715Z
---
Owner, 2026-11-19 in chat, after the macOS app's mirror of jlevy/metabrowser showed "main is now at 1d85c49 · Switch" at the foot of the nav pane:

"why should this happen at all? if I've opened a working directory it should stay the working directory. if I've opened a branch like main it should refresh because we mirror things? in cloud mode it shouldn't even be a choice? in local branch mode on a local repo ... I think we can follow the branch because if someone does a fetch, we would want the latest branch ... we generally want the UI to follow the state of the repo. The refresh button could trigger that, but then it would be a refresh button, not a 'switch' button."

The rule this replaces: "a refresh never moves the page under you" (thin-mirror plan 2026-09-23; docs/browsing-history.md, docs/command-line.md, arch-mirror-acquisition-and-refresh.md, source-pin-guard.js header). Today:
- Mirror on a branch: a refresh moves the ref, MirrorSession._observe_tip records `latest`, and source-freshness.js `describe` offers kind "switch". Meanwhile the mirror's Commits tab already walks the default branch's new tip (ServedMirror.default_tip), so Files and Commits disagree until Switch.
- Folder, working tree: live through the watcher; no offer. Correct.
- Folder, revision of a branch: "a branch that moves while it is shown is not followed" (arch-source-sessions-and-pins.md, Not yet); no status poll, no offer.

Target model: what the reader opened decides whether the view moves. A branch follows its branch; a commit ID stays; the working tree is always live. The children carry each part.
