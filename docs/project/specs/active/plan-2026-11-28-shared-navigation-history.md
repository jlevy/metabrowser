# Feature: Shared Navigation History and Native URL Controls

**Date:** 2026-11-28 (last updated 2026-11-28)

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Draft for review

## Overview

A reader who opens **Browse code** from a pull request should be able to return to the
exact PR view and then go forward to the code again.
The same rule applies when moving among files, commits, pull requests, stacks, and views
of those items. The browser already exposes its history through its toolbar, keyboard,
and gestures. The macOS app should make the equivalent actions visible and offer the
current Metabrowser address for copying or opening in a browser.

## Goals

- Restore the same item, view, and document location through Back, Forward, direct
  links, and reload in both hosts.
  Restore reading position when a history entry saved it.
- Use one route grammar and one set of rules for when a navigation adds, replaces, or
  restores an entry. Let the browser or WebKit own the history stack in its window.
- Keep the native Back and Forward controls, menus, keyboard shortcuts, and gestures
  consistent. Make the current internal address available without crowding the title bar.
- Define what happens on a Git source switch, a missing historical target, and a native
  server restart that changes its local origin.

## Non-Goals

- An application-wide timeline across separate windows and folders.
- A general-purpose browser address bar or an editable URL field in the window title.
- A durable external link for every local file or Metabrowser-specific view.
- Persistent Back and Forward stacks across app relaunch or WebView recreation.

## Background

The navigation footer previously linked to the PR whose head the server was serving.
It provided a way to return to that PR from a file or commit.
Once routine fetch timing moved to the Refresh tooltip, the link appeared on its own and
read like a status message.
The [footer cleanup](https://github.com/jlevy/metabrowser/pull/926) removes that
shortcut. The PR and code pages already participate in ordinary history.
Browse code opens a route in the same browsing context, including through a document
navigation when serving the PR head requires a source switch.
An initial deep link has no earlier entry in a fresh window.

The
[browser route grammar](../../architecture/arch-views-models-routes.md#browser-url-grammar)
separates the kind and identity of an item from its presentation and its fragment.
File routes, commit routes, the PR list and PR views, and stack views already have
shared addresses. The shell opens supported links in place.
The files navigator, top-level tab controller, and PR and stack controllers currently
participate in writing or restoring history.
History state also holds browser-local context such as the reader’s position or which
panel owns an otherwise identical landing address.
[In-App Link Resolution](plan-2026-11-26-in-app-link-resolution.md) defines the rule
that an ordinary click should open the same address a copied link names.

The current distinction between address and source is important.
A `/view/<path>` address is relative to the source the server is serving.
In the checkout selector Chrome test, Back after switching from a tag to the working
tree restores the earlier path against the working tree.
The source-pin guard detects stale restored documents and reloads against the source
being served. It does not restore the earlier tag.
Choosing a source and navigating inside it need separate semantics so that history can
restore an explicit source choice without changing another window’s source.

The [macOS app](../../../macos-app.md) wraps the same web UI. Its main window already
has **View > Back** and **View > Forward**, bound to Command-[ and Command-], and WebKit
navigation gestures.
Its GitHub web popover already has accessible history buttons and a read-only location
with Copy Link. The main window has a folder chooser in the title bar and **File > Open
in Default Browser**, using the current server URL. The native `PageAddress` stores the
encoded path, query, and fragment separately from the server origin.
A server restart may select a different port.
Discarding a background WebView can already discard its history.

## Design

### Shared Routes and History

Use the current address as the input to the same route dispatcher on direct open,
reload, Back, and Forward.
Give each route owner its selection and a navigation intent.
Converge the existing writer rules where they disagree before changing route ownership.
Keep history-only state under its existing owners and merge it when updating an entry.
A new entry must not inherit reading position or intent from the prior entry.
The address carries information another browser or window needs to open the target.
History state can carry transient anchors, scroll, or other restoration details.

| Intent | History behavior |
| --- | --- |
| Open another item, page tab, comparison file, or explicit fragment | Push once. Back and Forward restore both destinations. |
| Browse code or make a source selection that requires a document navigation | Let the document navigation add the entry once. Use the shared route rules on arrival. |
| Refresh, update live data, normalize an accepted route, or update reading position | Keep the entry. Replace only when its canonical address or owned state changes. |
| Keyboard preview or skim inside a list | Keep the current preview entry. A deliberate open uses the same rule as clicking. |
| Open the current target again | Keep its entry and reading position. Reveal it in the appropriate navigation panel if the action requests a reveal. |
| Back or Forward | Restore the selected entry. Cancel outstanding work for the previous selection. |
| Open in another window or tab | Start that browsing context with the same address and its own history. |

Preserve encoded path segments, ordered query values, and fragments.
Go directly to the requested PR or stack tab, commit diff file, named heading, or line
when the route supports it.
An address with no valid destination should show the appropriate error with its original
selection intact so the reader can still go Back or Forward.
A reload after a stale-page guard must settle once without adding another history entry.
If fault recovery or view replacement is asynchronous, only the current destination can
update the pane, URL, or reading position.

### Source Identity

Ordinary root-relative file routes continue to mean the server’s current source.
Following a branch or PR when it moves is an update to that source.
An explicitly fixed commit stays fixed.
A working tree remains live, even when reached again by Back.
History does not promise a historical snapshot of its uncommitted contents.

The proposed target for an explicit source selection is a source-qualified, reloadable
address. A named branch or PR head follows that named ref.
A fixed commit addresses its exact revision.
A working tree selector resolves against the checkout served by that session.
Resolve historical targets for the requesting view or use an existing source-scoped
destination. Keep source selectors separate from presentation fields.
Implement the encoding only after checking the shared server’s pin model, cross-window
effects, and the existing GitPath and trust rules.
A Back or Forward landing must not silently change another window’s source.
If a ref or object is gone or the session lacks access, show that failure in the current
entry and leave the reader’s other history entries usable.

Until there is a scoped source address, keep and document today’s behavior for
unqualified addresses.
Do not expose an unqualified address as an exact revision link.
An explicit pin switch through Browse code must still leave a usable Back path to the
PR, including when the pin guard reloads it.

### Browser and Native Controls

In a browser, leave Back, Forward, and the address bar to the browser.
Retain normal link actions such as modifier-click, Copy Link, and Open in New Tab.
Do not consume the browser’s history shortcuts or insert a second set of controls into
the page.

In the main macOS window, add visible Back and Forward controls to the native chrome.
Use the title-bar layout and the popover’s controls as references.
Verify that the folder chooser and the controls fit the minimum window width, and give
the controls distinct, accessible labels and disabled states.
Bind them to the current folder page’s WebView and the same actions as the **View**
menu. Keep Command-[ and Command-] and swipe gestures.
Verify correct dispatch when focus is in the pane, an editable field, the title bar, a
modal sheet, or a popover.
The action applies to the currently active browsing context.

Rebind availability when the active page or WebView changes.
An in-place route change must update the native controls and current address using
WebKit’s observed state.
If WebKit misses a same-document update, use a route-change notification to refresh the
display. History traversal remains WebKit’s. Folder or window switching must not join
histories, and a page temporarily given a different host retains only its own browsing
history.

If the local server restarts on a different origin, save the current relative
`PageAddress` and re-open it on the new origin.
Reset obsolete WebKit history for that context so stale old-port items cannot enable
Back or Forward. A same-origin reconnect keeps usable history.
A regular browser tab on a stopped origin follows the browser’s own behavior.

### Current URL and API

In the macOS host, expose the validated current Metabrowser URL in native chrome, with
**Copy Current URL** and the existing **Open in Default Browser** action.
Make the full address available without hiding meaningful query values or position
anchors behind the folder title.
Use a compact read-only presentation, with enough room to inspect the whole URL on
demand. Never show or copy bootstrap credentials.
Actions are disabled while no validated current server page is available.
A local URL works in an authorized browser on the same machine while that server is
running. **View on GitHub** continues to name its own provider counterpart where
available. Keep the two meanings distinct, particularly for uncommitted files and
Metabrowser-only views.

The native controls can build on `FolderPage`, `PageAddress`, and the active WebView’s
URL and history availability.
No fetch or pin API change is needed for those controls.
If scoped source addresses require server support, define and test that route contract
first. Reuse existing Git and source validation, and retain the ordinary routes for
existing links. No history stack crosses the process boundary.

## Implementation Plan

### Phase 1: Shared History Contract and Native Controls

- [ ] Record browser and WebKit behavior for the same route and intent table.
  Fix the mismatches at the shared route boundary and keep same-document state intact.
- [ ] Add native Back and Forward and current URL actions.
  Cover page swapping, disabled state, key dispatch, and recovery to a new server
  origin.
- [ ] Verify Browse code and its return from an ordinary PR, a PR Changes file, and a
  Guided Review step. Document the actual URL and history behavior.

### Phase 2: Explicit Source History

- [ ] Specify the source selector spelling and how a route can be served without
  mutating other windows or changing the meaning of existing addresses.
- [ ] Implement source-aware restoration and copying for explicit selections.
  Test branch movement, a fixed revision, a working tree, and unavailable refs.
- [ ] Update route grammar, browserless evidence, user guides, and macOS help.

## Testing Strategy

1. Extend the browserless route and source-history sessions to replay open, replace, and
   history landing across Files, Commits, the Pulls list, PR tabs, stack tabs,
   comparisons, and headings or lines.
   Include same-address state, rapid traversal, refresh without duplicate entries, and
   stale pin recovery. Verify source addresses through a direct server request and the
   project CLI route surface.
2. Run the same PR → Browse code → Back → Forward trace in real Chromium and the native
   WebKit host. Check URL, selected tab or file, reading position, and navigation
   selection after each step.
   Cover both an already served PR head and a Browse code link that switches sources.
   Open a copied address in a fresh, authorized browsing context on the same server.
   Verify the view with the source the server currently serves.
   Phase 2 also verifies that a source-qualified copy restores its intended source after
   another source has been selected.
3. Verify native buttons, menu items, shortcuts, gestures, and their enabled states with
   and without prior history.
   Cover editable focus, a modal, popovers, multiple windows, page discard, and a
   restart on a different port.
   Confirm that copying and opening the current URL tracks in-place changes and that an
   invalid or retired origin never gets copied.
4. Keep the checkout Back case in Chrome as the baseline for unqualified addresses.
   Add source-qualified cases in both engines.
   Open two windows on the same server and verify that restoring one window’s explicit
   source leaves the other window on its own target.

## Rollout Plan

Land the footer cleanup separately.
Review the shared history contract and native controls together, then address explicit
source history as its own phase.
Update the browser route and macOS user documentation alongside each behavior change.
No migration of stored Back and Forward stacks is needed.

## Open Questions

- Which compact placement exposes the native URL while preserving the folder chooser and
  fitting the minimum window width?
  Compare existing native title-bar and location patterns in a WebKit prototype.
- Which source-qualified address can be served independently of the mutable session pin?
  Resolve server and route ownership before choosing the encoding.

## References

- [Browser URL grammar](../../architecture/arch-views-models-routes.md#browser-url-grammar)
- [In-App Link Resolution](plan-2026-11-26-in-app-link-resolution.md)
- [Switching folders in the macOS app](plan-2026-11-18-macos-folder-switching.md)
- [Metabrowser for macOS](../../../macos-app.md)
- [Navigation reveal in Chromium](../../../../tests/dom/nav-reveal-chrome.mjs)
- [Checkout source and Back behavior in Chromium](../../../../tests/dom/checkout-ref-selector-chrome.mjs)
- [Native page and actions](../../../../apps/macos/Sources/Metabrowser/FolderPage.swift)
- [Native popover controls](../../../../apps/macos/Sources/Metabrowser/WebPane.swift)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
