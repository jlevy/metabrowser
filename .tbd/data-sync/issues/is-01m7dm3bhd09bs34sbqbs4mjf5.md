---
type: is
id: is-01m7dm3bhd09bs34sbqbs4mjf5
title: Cmd-R always reloads, in the app and the browser, and is documented
kind: bug
status: in_progress
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-14T18:11:17.164Z
updated_at: 2026-11-14T18:11:19.674Z
---
The user (2026-11-14): "we should make sure cmd-R always reloads and that this is documented."

The macOS app has View > Reload Page on Cmd-R (MainMenu.swift, BrowserWindowController.reloadPage), and the web shell's shortcut registry disqualifies keys with Cmd, Ctrl or Alt. Find every state where Cmd-R does not reload (the window's status view while the server starts or fails, a discarded web process, focus in an input or the Quick Search field, a sheet, menu validation disabling the item, and in a plain browser any page handler that swallows it) and make it reload in each, or say why a state cannot.

Done when Cmd-R reloads in every state, a test pins it (Swift menu validation and the web registry ignoring modified keys), and the Keyboard Shortcuts section in docs/design-system.md, the help overlay if it lists browser keys, and apps/macos/README.md document it.
