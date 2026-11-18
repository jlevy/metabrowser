---
type: is
id: is-01m7regj6mpxdzr60zmvmp0fhw
title: "macOS app test target: pin the window controller's lifetime and menu forwarding"
kind: task
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-18-macos-folder-switching.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7ressh43myae3chm9e1hvf8
parent_id: is-01m7r5cmz107gb7jxq0y6pp7fe
created_at: 2026-11-18T23:05:17.253Z
updated_at: 2026-11-18T23:10:19.683Z
---
Deferred from Review A, finding A1 (Medium), on jlevy/metabrowser#566 (FolderPage split from BrowserWindowController). The layer fixed A1 with hand checks (docs/project/qa/qa-macos-app-hand-checks.md, "Menu Actions and Closing a Window"); this bead is the automated half, the review's option (a).

The package's only test target is ShellCoreTests, which cannot see FolderPage or BrowserWindowController, so nothing automated pins:
- a controller from FolderSession.makeWindow stays alive after its caller returns (BrowserWindowController.open; AppKit holds a window's controller and delegate weakly, NSWindow.h). The first commit of #566 broke this and every test passed.
- after window.close(), the controller is released and session.pages is empty.
- controller.supplementalTarget(forAction: #selector(FolderPage.reloadPage(_:)), sender: nil) === controller.page, and controller.page.view.nextResponder === controller.page.

An offscreen AppKit probe (no app launched) confirmed the mechanism on macOS 26: the chain from the page's view is view -> page -> host view -> window -> controller, and without the table the controller is released as soon as its creator's scope ends.

What it takes: a .testTarget depending on the Metabrowser executable target (@testable import); a FolderSession built from a test RuntimeSetup and LaunchGate, which starts nothing until asked; an NSWindow that is never ordered in. FolderPage makes a WKWebView, so the suite must join webkit_suites in apps/macos/Makefile (WebKit's startup stalls the main actor). NSApp.target(forAction:to:from:) still needs a key window, so an active app; pin supplementalTarget and nextResponder directly and keep the hand check for AppKit's own dispatch. Check that nothing the test builds reads or writes the user's saved session or logs folder (AppIdentity in a test process).
