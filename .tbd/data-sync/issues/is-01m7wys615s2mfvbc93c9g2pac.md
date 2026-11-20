---
type: is
id: is-01m7wys615s2mfvbc93c9g2pac
title: Branch chooser and ref selection
kind: epic
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-20T17:06:34.659Z
updated_at: 2026-11-20T17:06:34.659Z
---
The Files toolbar's chooser switches a view between branches, tags, commits and pull request heads, in a mirror or beside a checkout's working tree. Landed: the chooser in the toolbar (#577), a local checkout's branch and tag chooser (#559), every ref newest first (#614), scroll kept across refills (#625), and a branch that heads a pull request shown with it (#651).

What remains is the follow-ups from those reviews: switching state after a bfcache restore (mb-0c3a), telling a repository's own pull requests from a fork's (mb-n3hm), redrawing the toolbar around the chooser (mb-k1sx), refused-request windows on other pin switches (mb-ayxi), the Commits landing's HEAD check (mb-8oy4), and the working-tree and branch-snapshot Files workflow (mb-itzy, deferred). Following a branch when the repository moves is the epic mb-2uut.
