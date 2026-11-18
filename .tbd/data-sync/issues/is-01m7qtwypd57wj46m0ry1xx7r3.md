---
type: is
id: is-01m7qtwypd57wj46m0ry1xx7r3
title: "Flake: macOS PageRevealWebKitTests and PagePrintTests time out waiting for loads (CI and loaded machines)"
kind: bug
status: closed
priority: 2
version: 4
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-18T17:22:31.755Z
updated_at: 2026-11-18T22:35:26.168Z
started_at: 2026-11-18T21:02:21.019Z
closed_at: 2026-11-18T22:35:26.167Z
close_reason: "Root cause fixed in #576 (6d7aae3ae): an early WKDownload cancel ended WebKit's network process"
resolution: null
duplicate_of: null
---
#546's 'macOS 26, Xcode 26.6' job at 9a6679abd (run 44355710866) failed many PageRevealWebKitTests (commits/failures never arrive within 'eventually') and PagePrintTests (watcher.loaded never true; then a WKErrorDomain Code=4 TypeError). The same tree's predecessor b15cd93d3 passed, and #539 at c173d2eee, which contains the same main, passed. An agent saw PageRevealWebKitTests time out locally at load average ~70 and pass on rerun. Find the wait bound in 'eventually' for these tests and whether WebKit loads are slow under load or stuck; fix the wait, not the assertion.

## Notes

Root cause (PR #576): DownloadTests.aCancelledReplacementKeepsTheOriginal cancelled its WKDownload before WebKit's network process reported the destination; the test process then logged the fault 'Received an invalid message DownloadProxy_DidCreateDestination from the Networking process' and WebKit ended the network process, failing every page load in flight in the shared WebKit test process (WebKitErrorDomain 300, plus 102 for held responses). Those loads never commit, so tests waited out eventually's 30 s. Not a timeout, contention, server-readiness, or PageReveal ordering bug. Fix: cancel after download.progress.completedUnitCount > 0 (fault 5/10 standalone runs -> 0/20); page-load tests fail at once with NetworkProcessLost carrying WebKit's log. The app never cancels a WKDownload; DownloadCoordinator.cancel documents the rule.
