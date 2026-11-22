---
type: is
id: is-01m7v8bs62dz0nqmqb9rnhgsdb
title: "Branches follow the repository: a view of a branch tracks it in mirror and folder modes; a commit or the working tree stays put"
kind: epic
status: open
priority: 1
version: 17
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/631
    at: 2026-11-20T19:14:52.177Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/632
    at: 2026-11-20T19:14:52.178Z
delegate: claude-code@spud10.local
labels:
  - linear
  - Feature
dependencies: []
child_order_hints:
  - is-01m7v8ctk4af96q7ykmb5psdd7
  - is-01m7v8cv4e6sjryervx72qmn90
  - is-01m7v8cvnhxhpd84rsjmtqqrm3
  - is-01m7v8d2dzrf8cg3wrxezg9bh1
  - is-01m7v8prb166f74m9855fmntda
hold: null
hold_until: null
created_at: 2026-11-20T01:15:32.417Z
updated_at: 2026-11-22T21:18:39.891Z
started_at: 2026-11-20T01:17:55.715Z
duplicate_of: null
extensions:
  linear:
    id: 77827478-a935-4840-ae95-ebfb068a7f1d
    linked_at: 2026-11-20T18:02:02.533Z
---
Owner, 2026-11-19 in chat, after the macOS app's mirror of jlevy/metabrowser showed "main is now at 1d85c49 · Switch" at the foot of the nav pane:

"why should this happen at all? if I've opened a working directory it should stay the working directory. if I've opened a branch like main it should refresh because we mirror things? in cloud mode it shouldn't even be a choice? in local branch mode on a local repo ... I think we can follow the branch because if someone does a fetch, we would want the latest branch ... we generally want the UI to follow the state of the repo. The refresh button could trigger that, but then it would be a refresh button, not a 'switch' button."

The rule this replaces: "a refresh never moves the page under you" (thin-mirror plan 2026-09-23; docs/browsing-history.md, docs/command-line.md, arch-mirror-acquisition-and-refresh.md, source-pin-guard.js header).

Target model: what the reader opened decides whether the view moves. A branch follows its branch; a commit ID stays; the working tree is always live. The children carry each part.

Where it stands (2026-11-22):

* Done, #632 (mb-pq8y): a mirror's pin on a branch follows the branch when a refresh moves it, and Refresh replaces the Switch offer, so Files and Commits agree.
* Done, #631 (mb-30xb): one mirror per repository, so opening a pull request or any URL inside a repository reuses that repository's mirror.
* Correct as it was: a folder's working tree is live through the watcher.
* Not built: a revision of a checkout's branch in folder mode does not follow the branch (mb-0qgm).
* Waiting on the owner: whether Refresh in folder mode may fetch (mb-gkq1), and whether a pull request's served head and its Changes diff follow new pushes (mb-qp3s).
* How soon a followed branch follows: a mirror refreshes only once its last fetch is a freshness window (60 s) old, so a push shows up to about 90 s later. mb-6pzh, under the update cadence epic mb-dip2 (OS-627), brings that to seconds.

## Notes

2026-11-19 owner (chat), the governing principle: "using Metabrowser in Cloud Mirror mode should be much like using it on the web on github.com. You're browsing everything as of the current data. When using in local mode, it is blended, with an extra layer of the current working tree but the cache layers are still the same as mirror mode." So a mirror shows current data the way github.com does: a branch is its latest commit, never a stale one behind an offer. A repository folder is the same revision layer plus the live working tree. Each child (mb-pq8y, mb-0qgm, mb-gkq1, mb-qp3s, mb-30xb) is judged against this.

2026-11-20 audit: #631 (one mirror per repository) and #632 (a served mirror branch follows its ref) are merged. Open: folder mode's branch follow (mb-0qgm) and two owner decisions (mb-gkq1: may Refresh fetch in folder mode; mb-qp3s: do a pull request's head and Changes follow new pushes).

2026-11-22 check: nothing under this epic is active (no claimed bead, no open pull request), so it is open again rather than in progress, per docs/development.md. Description brought up to date. Added mb-6pzh (under mb-dip2) for how soon a mirror branch follows a push.
