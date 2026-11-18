---
type: is
id: is-01m7qtwypd57wj46m0ry1xx7r3
title: "Flake: macOS PageRevealWebKitTests and PagePrintTests time out waiting for loads (CI and loaded machines)"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-18T17:22:31.755Z
updated_at: 2026-11-18T21:02:21.023Z
started_at: 2026-11-18T21:02:21.019Z
---
#546's 'macOS 26, Xcode 26.6' job at 9a6679abd (run 44355710866) failed many PageRevealWebKitTests (commits/failures never arrive within 'eventually') and PagePrintTests (watcher.loaded never true; then a WKErrorDomain Code=4 TypeError). The same tree's predecessor b15cd93d3 passed, and #539 at c173d2eee, which contains the same main, passed. An agent saw PageRevealWebKitTests time out locally at load average ~70 and pass on rerun. Find the wait bound in 'eventually' for these tests and whether WebKit loads are slow under load or stuck; fix the wait, not the assertion.
