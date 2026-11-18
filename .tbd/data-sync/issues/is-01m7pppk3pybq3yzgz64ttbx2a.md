---
type: is
id: is-01m7pppk3pybq3yzgz64ttbx2a
title: "Chrome drivers: waitFor expressions read document.documentElement unguarded during navigation"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-18T06:49:54.549Z
updated_at: 2026-11-18T06:49:54.549Z
---
#544's shortcut-strip test failed on CI (chrome 3.13 1/4 at aa3b77e82) because a waitFor poll ran while Page.navigate replaced the document and documentElement was null; fixed there in f4b8a185d with optional chaining. The same unguarded pattern is in tests/dom/folder-home-chrome.mjs:145 and possibly other drivers. Fix: either guard each expression, or have chrome-session.mjs waitFor treat an exception thrown during a navigation as not-yet-ready (keep rethrowing at the deadline with the last error).
