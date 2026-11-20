---
type: is
id: is-01m7sad08dwewgwt3hjpqp1fzv
title: "macOS app: a GitHub link opens its mirror as a tab of an open checkout of that repository"
kind: feature
status: closed
priority: 2
version: 6
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/607
    at: 2026-11-20T17:01:44.472Z
delegate: claude-code@spud10
labels:
  - linear
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T07:12:40.717Z
updated_at: 2026-11-20T17:01:44.474Z
started_at: 2026-11-19T07:12:45.935Z
closed_at: 2026-11-19T07:58:32.657Z
close_reason: Merged in https://github.com/jlevy/metabrowser/pull/607 (9ea09a944).
resolution: null
duplicate_of: null
---
A GitHub URL sent to the app or entered in Open URL… opens its mirror (the owner's 2026-11-18 decision). When no mirror window is open for that repository but a window of a local checkout whose origin is that GitHub repository is, the new mirror window joins that window as a tab instead of opening alone. metab reports a folder's GitHub repository in GET /api/identity (repository). Several matching windows: the one shown most recently.

## Notes

PR: https://github.com/jlevy/metabrowser/pull/607. Several matching windows: the checkout shown most recently wins. Close when the PR merges.
