---
type: is
id: is-01m77c8dca6jc49rzynzf37bsf
title: "macOS app: a stale WebKit callback must not change a newer window status (review E1, #363)"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels:
  - macos
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T07:58:47.689Z
updated_at: 2026-11-12T08:07:36.762Z
started_at: 2026-11-12T07:58:53.716Z
closed_at: 2026-11-12T08:07:36.760Z
close_reason: "Fixed in 80567cbc on claude/v1-final-review-lifetimes: PageReveal (ShellCore) ties reveal and page-error callbacks to the WKNavigation load returned; every covering status supersedes and stops it. PageRevealTests and PageRevealWebKitTests red against the transcribed Boolean, green after."
resolution: null
duplicate_of: null
---
Review E1 on #363 (mb-niod): pages.cancelAll() invalidates loads still waiting to submit, but not a navigation already submitted to WebKit. showFailure/showStarting neither stop it nor clear revealOnCommit, so a late didCommit hides the failure and Retry, and a late provisional failure replaces the server's diagnostic. Fix: tie status-changing callbacks to the navigation load submitted (ShellCore PageReveal), stop it when server state supersedes it, regression tests.
