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
Title-bar clicks act on that window’s current folder page.
Menu shortcuts use native responder targeting, so an active web popover can traverse its
own history. Keep the address disclosure separate from browsing history and honor active
sheets. Availability uses the same page-visible and history conditions as the View menu.
Keep text editing shortcuts inside the selectable URL and respect the active input
source.

Rebind availability when the active page or WebView changes.
An in-place route change must update the native controls and current address using
WebKit’s observed state.
If WebKit misses a same-document update, use a route-change notification to refresh the
display by asking native code to reread the active WebView’s state.
History traversal remains WebKit’s. Folder or window switching must not join histories,
and a page temporarily given a different host retains only its own browsing history.

If the local server restarts on a different origin, save the current relative
`PageAddress` and re-open it on the new origin.
Reset obsolete WebKit history for that context so stale old-port items cannot enable
Back or Forward. A same-origin reconnect keeps usable history.
A regular browser tab on a stopped origin follows the browser’s own behavior.

### One Row in the macOS Title Bar

Use the existing title row.
In leading-to-trailing order, place the system window buttons, the existing project
chooser, Back and Forward, a flexible read-only URL field, and the Metabrowser project
mark. Keep a real window-drag region beside the field.
The chooser identifies the project and opens its folder and represented-path menus.
The arrows come after it because they navigate within that project’s page history.
The URL field describes the current page within that history.

```text
Wide:     ● ● ●   example-project ⌄   ‹ ›   [ 🔗 127.0.0.1:8457/view/docs/architecture.md#L42 ]      ◇
480 pt:   ● ● ●   example-proj… ⌄   ‹ ›   [ 🔗 /view/…/architecture.md#L42 ]      ◇
```

The current main window has a 480 pt minimum and an approximately 36 pt trailing mark
accessory. For the sketch, allow 76 pt through the first gap after the system window
buttons, 56 pt for the history pair, 126 pt for the chooser, 36 pt for the mark, and 40
pt for remaining gaps and drag space.
That leaves about 144 pt for the URL at the minimum, allowing for borders.
At 760 pt a wider 174 pt chooser leaves about 376 pt.
The existing mark’s layout tests record a 32 pt bar.
Use the width budget as an estimate until the AppKit prototype measures the actual row
and content rectangle.
Preserve the existing content height and minimum window width.

Let the full origin drop out of the resting field as space tightens, then elide the
middle of the path where possible so the selected item remains recognizable.
Keep both history buttons in fixed positions and disable each independently.
Give each its own accessible name and keyboard focus.
Keep the folder chooser usable if its visible name truncates.
If system metrics or localization make the address text too narrow to read, shorten it
to an address-details button and keep the link icon available for direct copying.
Keep a readable URL field at 480 pt in the ordinary layout, with the copy icon inside
the field’s width.

Start with one window-owned leading accessory that lays out the chooser, history pair,
and URL together. Keep the existing independent trailing mark.
Give the chooser an assigned width so its current self-sizing leaves room for the URL.
Evaluate an AppKit unified compact toolbar if the leading accessory cannot meet the fit
or accessibility criteria.
Either implementation must keep real system window buttons, drag and double-click
behavior, the folder chooser’s represented-path menu, fullscreen behavior, and
accessibility. Avoid giving the chooser and URL separate requests for all remaining
space. Measure fit in both appearances, with long folder names and larger text.
Exercise title-bar drag, click, and focus behavior with the disclosure open.

### Conventions and Shortcuts

- **Safari and Chrome** both use Command-[ and Command-] for page history.
  Safari also offers a compact toolbar layout.
  Chrome offers Command-arrow aliases.
  Metabrowser already owns the brackets in its **View** menu.
  Keep them and WebKit’s existing navigation gestures.
  Leave Command-arrow to normal text navigation.
  [Safari web-app shortcuts](https://support.apple.com/en-gb/guide/safari/ibrw3ceda9e7/27.0/mac/27)
  ·
  [Safari shortcuts](https://support.apple.com/guide/safari/keyboard-shortcuts-and-gestures-cpsh003/mac)
  ·
  [Safari toolbar](https://support.apple.com/en-euro/guide/safari/ibrw1012/27.0/mac/27)
  · [Chrome shortcuts](https://support.google.com/chrome/answer/157179?hl=en)
- **Arc and Dia** retain direct history actions in more compact browser chrome.
  Arc exposes an optional toolbar and a command for copying the current URL. Dia’s
  documented history controls and gestures reinforce keeping the buttons obvious even
  when other toolbar items move.
  [Arc toolbar notes](https://resources.arc.net/hc/en-us/articles/20498377604887-Arc-for-macOS-2023-Release-Notes)
  · [Arc commands](https://start.arc.net/command-bar-actions) ·
  [Dia product updates](https://www.diabrowser.com/changelog)
- **ChatGPT desktop** documents Command-[ and Command-] for in-app history, along with
  mouse Back and Forward.
  **Claude desktop** publicly documents a separate Code session switcher using shifted
  brackets. Its public material reviewed here does not establish the main window’s global
  history keys. In both comparisons, distinguish revisiting an item from changing which
  workspace or session is selected.
  [ChatGPT desktop commands](https://learn.chatgpt.com/docs/app/commands) ·
  [Claude desktop guide](https://academy.claude.com/tutorials/navigating-the-claude-desktop-app)
  ·
  [Claude Code desktop shortcuts](https://code.claude.com/docs/en/desktop#keyboard-shortcuts)
- **Metabrowser** already assigns Command-L to **File > Open URL…**. Keep that command
  and binding. The read-only field participates in native keyboard navigation.
  Pressing the address text opens a disclosure with a selectable full URL and **Open in
  Default Browser**. Escape returns focus to the field.

### Bare Brackets and Native Key Hints

Keep Command-[ and Command-] as the native menu shortcuts.
In the macOS app, allow unmodified `[` and `]` when the active project can navigate in
that direction.
Match literal characters from the current input source with all modifiers
clear, and ignore auto-repeat.
Leave brackets to editable controls, IME composition, and the URL disclosure, and leave
shifted braces and other chords alone.
Browser windows retain their own navigation controls and shortcuts.

With focus in the project’s embedded page, the web shortcut registry handles the bare
keys with its existing focus and modal checks.
Add both brackets to the registry’s character vocabulary and register the commands only
when the native host offers the action.
Give the registry availability for each arrow and send the navigation intent to the
focused native window’s existing actions.
Scope the bridge to the active local main frame.
The AppKit responder owns native chrome focus.
Only the focused surface handles an event; Command brackets still use the normal menu
path.

Hold Shift alone to reveal `[` and `]` in yellow keycaps beside the available arrows,
alongside the page’s own shortcut hints.
Reuse the web reveal’s hold and cancellation rules, including the current 200 ms
threshold. Mirror the registry’s published reveal state while the page owns focus.
Native chrome uses the same rules while it owns focus.
Only the current focus owner runs a timer.
Clear state when ownership changes and discard delayed messages from the old focus
owner. Clear the reveal on release, an unhandled key or chord, pointer press or scroll,
text focus, or window deactivation.
Release Shift before pressing a bare bracket.
Match the web keycaps’ colors and placement in both appearances.
Overlays leave layout, hit targets, and accessibility focus intact.
The persistent arrow tooltips and accessible shortcut descriptions list both bindings.

### Back and Forward History Menus

A short click traverses one entry.
Click and hold an enabled arrow to open that direction’s native history menu, following
Safari’s pattern. Secondary click opens the same menu.
Expose it to keyboard and VoiceOver through **View > Back History** and **View > Forward
History** even when the toolbar is out of focus.

Show the nearest reachable entries first.
Read the current project WebView’s `WKBackForwardList`, reverse its Back entries, and
keep its Forward entries in order.
Use the page title and add route context where titles repeat or are unavailable.
Jump to the selected WebKit item with `go(to:)`, preserving exact route and in-page
state. Closing the menu does not navigate, and releasing the hold does not trigger an
extra step. Before activation, revalidate the original hosting window, WebView, origin,
current history item, and the chosen item’s presence in that direction.
Dismiss stale menus if any check fails.
Use entry identity so visits that share a URL retain their own history state.
A new navigation after Back clears the forward branch as usual.

[Safari history controls](https://support.apple.com/guide/safari/keyboard-shortcuts-and-gestures-cpsh003/mac)
·
[WebKit’s history list](https://developer.apple.com/documentation/webkit/wkbackforwardlist)
·
[Jump to a history item](https://developer.apple.com/documentation/webkit/wkwebview/go%28to%3A%29)

### Current URL and API

In the macOS host, expose the validated current Metabrowser URL in native chrome, with
**Copy Current URL** and the existing **Open in Default Browser** action.
Click the field’s link icon to copy the full URL directly.
Its tooltip reads “Internal Metabrowser server URL · Click to copy”.
Give the icon an accessible **Copy internal Metabrowser server URL** label and show a
brief **URL copied** confirmation on success.
Clicking the address text still opens its details.
Make the full address available without hiding meaningful query values or position
anchors behind the folder title.
Use a compact read-only presentation, with enough room to inspect the whole URL on
demand. The display and actions require a ready server endpoint and a visible, committed
main document at that origin.
Preserve the separate address used for recovery.
Close the disclosure and clear its address when the committed page becomes unavailable
or the window hosts another page.
Validate again when copying or opening, preserve URL encoding including bracketed IPv6
hosts, and exclude bootstrap credentials.
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
   Click the link icon and verify the exact clipboard contents without opening the
   address disclosure. Exercise bare brackets and the synchronized Shift hints with page,
   native chrome, and text focus.
   Verify that braces, IME composition, and disabled directions leave the page alone.

4. Keep the checkout Back case in Chrome as the baseline for unqualified addresses.
   Add source-qualified cases in both engines.
   Open two windows on the same server and verify that restoring one window’s explicit
   source leaves the other window on its own target.

5. In the native trace, open Back and Forward history by holding and by keyboard.
   Check nearest-first order, jump to a non-adjacent item, and cancel a menu without
   navigating. Cover repeated URLs with different history state and a history branch that
   changes while the menu is open.
   Then go Back and open a different route.
   Forward disables. Cover stale observations from a WebView replaced during a folder
   switch, a canceled provisional navigation, and an exact encoded URL with an IPv6
   origin. Measure the actual native row, drag region, and control hit targets while
   resizing. Confirm accessibility names and values, right-to-left layout with
   left-to-right URL text, and title-bar behavior in fullscreen.

## Rollout Plan

Land the footer cleanup separately.
Review the shared history contract and native controls together, then address explicit
source history as its own phase.
Update the browser route and macOS user documentation alongside each behavior change.
No migration of stored Back and Forward stacks is needed.

## Open Questions

- Does the leading accessory fit at minimum width and preserve the folder chooser and
  window behavior? Measure the AppKit prototype before settling the layout metrics.
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
- [Apple’s toolbar guidance](https://developer.apple.com/design/human-interface-guidelines/toolbars)
- [Native popover controls](../../../../apps/macos/Sources/Metabrowser/WebPane.swift)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
