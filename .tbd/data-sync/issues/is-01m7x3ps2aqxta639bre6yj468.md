---
type: is
id: is-01m7x3ps2aqxta639bre6yj468
title: "macOS title folder menu: the check mark of the current entry sits on the name's (first, bold) line, not centred across the two-line row, keeping the accessible checked state"
kind: bug
status: in_progress
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T18:32:38.727Z
updated_at: 2026-11-20T18:55:55.057Z
started_at: 2026-11-20T18:33:17.490Z
---
Owner 2026-11-20. Follow-up to mb-z822 (#628), which moved the cloud/folder icon to the name's line but kept the native check centred because a custom onStateImage loses AXMenuItemMarkChar (the accessible checked state). Find a way that puts the check on the first line and keeps the item reported as checked to accessibility (VoiceOver), with a test.

## Notes

PR #672 (claude/menu-check-first-line), head 1b69bd997. No prior notes on this bead, so nothing merged away.

Approach: the chooser's rows are TitleLineMenuItem (Sources/ShellViews): with a subtitle the check is AppKit's own checkmark symbol (13 pt bold small, ink centred at 6.375, 7.5 in a 13 x 16 slot) at the top of an image 2 x RootMark.TitleLineLayout.rise taller, so AppKit centres it on the title's line. Open menu, macOS 26.5.2: check ink centre 0.0 pt from the first title line's (was 7.0 below), 9.0 pt tall, menu width unchanged. The item overrides the legacy accessibilityAttributeValue(_:) so AXMenuItemMarkChar is what a stock item in the same state answers (a custom onStateImage otherwise makes it nil; accessibilitySetOverrideValue changes nothing).

Rejected, all measured on 26.5: NSMenuItem.view (Option alternate never swaps, highlight and tint are the view's to redo); NSMenu.showsStateColumn = false (native check still drawn); title paragraph or baseline tricks (the check is not in the title).

Tests: TitleLineCheckTests (parity with a stock item's mark char for every state and subtitle, directly and through the menu's AX children; the premise that a stock item with the raised check loses it; position, size, column width); four mutations each fail the intended test. ShellViews is now a ShellCoreTests dependency.

Not verified: no AX client (process not accessibility-trusted), so VoiceOver itself is a hand check (qa-macos-app-hand-checks.md step 17); no macOS 15 (package requires 26); screencapture is denied here, so screenshots are the menu window drawn into a bitmap (worktree attic/menu-check-*.png). make -C apps/macos test: all Swift suites pass; its script checks fail one case, the quarantine helper's, because xattr on PATH is a broken pyenv shim on this Mac.
