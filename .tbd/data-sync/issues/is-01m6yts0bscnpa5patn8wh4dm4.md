---
type: is
id: is-01m6yts0bscnpa5patn8wh4dm4
title: Dismiss the narrow Markdown Contents drawer with Escape
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-09T00:19:21.592Z
updated_at: 2026-11-09T00:19:21.592Z
---
The built-in browser on installed `0.11.1.dev1304+b2fb62099` opened the narrow Markdown Contents drawer from its button and closed it when a heading was selected. On a disposable long Markdown document, Escape did not close the reopened drawer in either of two attempts. The Markdown Reading Layout check in `docs/e2e-testing.md` expects Escape dismissal. Source inspection found no keydown handler in the installed inert TOC implementation.

Reproduce by opening a Markdown document long enough to show Contents, narrowing the preview until the rail becomes a drawer, scrolling past the first section, and opening the drawer. Press Escape while it is open. Verify that Escape closes it, clears the expanded state and restores focus to the toggle. Check the trusted and inert render paths and add a focused keyboard check for the documented behavior. Preserve opening and heading selection. Determine history and outside-click behavior separately if relevant; the observed scope is Escape dismissal.

Separate UI follow-up. Existing `mb-ddbe` covers toggle positioning while scrolling. Keep release and config/cache dependency scopes as they are.
