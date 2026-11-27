# Feature: Link Preview Tooltips

**Date:** 2026-11-26 (last updated 2026-11-27)

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Approved 2026-11-26 from the owner’s request; in implementation on a pull
request stacked on #891.

## Overview

A link in rendered text that opens a page in Metabrowser looks like any other link, so a
reader cannot tell, before clicking, what it opens or that it stays in the app.
This phase gives such a link a concise tooltip: what kind of object it opens, that
object’s title or description when the app knows it, and that it opens here.
Resting on the link also starts loading the page it opens, so the click is fast.
Tooltips on links follow one rule everywhere, documented in the design system.

It builds on [In-App Link Resolution](plan-2026-11-26-in-app-link-resolution.md), whose
resolver (`static/repository-links.js`) already decides what each link opens, and is
stacked on the pull request that opens route links in place (`mb-0uzt`).

The owner asked, on 2026-11-26:

> “With page-to-page linking, let’s make sure that we offer concise tooltips.
> We should be able to recognize what the object is and prefetch it if it’s on the link.
> And then the tooltip could show the title or the description of what the linked GitHub
> object is, if available.
> It would also make it clear that it’s a local link, so it’s easy to click without
> navigating away from metabrowser.”
> 
> “This should follow a consistent design system that aligns with everything else we’ve
> done, and we should be consistent on tooltips on links in general.
> And document the design system.”

## Goals

- A link the resolver opens in the app (a file or folder, a pull request or one of its
  tabs or changed files, a stack, a commit, the pull request list) shows, on pointer
  rest, a tooltip that names the object’s kind and identity, its title or description
  where known, and that it opens in Metabrowser.
- Resting on such a link prefetches what its click opens, within existing budgets.
- One documented rule for tooltips on links in general, in-app and external, in
  `docs/design-system.md`, held by a check where it can be.

## Non-Goals

- Tooltips on the app’s own chrome links whose text already says what they open (a Pulls
  row’s title, a crumb): the design system’s “Tooltips Add Information” keeps those
  without one.
- New GitHub requests made only to fill a tooltip.

## Background

The design system already fixes how a tooltip behaves
([One Tooltip, and It Is Ours](../../../design-system.md#one-tooltip-and-it-is-ours)
through
[A Surface Puts Away Only Its Own Tooltip](../../../design-system.md#a-surface-puts-away-only-its-own-tooltip)):
the app’s own tooltip and never `title`, only when it adds information, pointer-only,
placed on its anchor and holding still, and put away by the surface that showed it.
The Git panel’s commit hover card and the table plugin’s reference card are the existing
rich cards. [External GitHub Links](../../../design-system.md#external-github-links)
gives an outside GitHub link its mark.

## What Exists Today

A survey of `main` and #891 on 2026-11-26 found these pieces, each private to the
surface that owns it:

| Need | Exists | Gap |
| --- | --- | --- |
| A card in the app’s tooltip | `MetabrowserTooltip.show(html, anchor)` and `mb.tooltip.show`: one `.custom-tooltip`, a 300 ms appear delay (`TOOLTIP_APPEAR_DELAY` in `static/app.js`), placed once on its anchor | A visible tooltip does not take new HTML; a `show` still waiting out its delay does, and keeps its time ([A Tooltip Holds Still](../../../design-system.md#a-tooltip-holds-still)) |
| Which links are in-app | `enhance` and the Markdown enhancer keep each link’s answer by identity (`opens`, `internalTargets`, `routeTargets`) | No registry another module can read; the `data-metabrowser-github-localization` attribute is forgeable in a trusted render |
| A pull request’s title and state | `GET /api/plugin/github/pulls?q=<n>`, the catalog’s exact-number search (`pull_catalog.py` `catalog_search`), cache-only, about 1 ms | No client cache or export; `listedState` in `pull-state.js` is the github plugin’s own |
| A commit’s subject | `GET /api/git/commit/<id>`, one `git show`, never a fetch; `fetchCommitDetail`’s cache in `static/git-panel.js` | Private to the Commits panel |
| A stack | “Stack #N” (`stackLabel` in `pull-stacks.js`), its members from the cache-only stacks route | Plugin-internal |
| A file or folder | Its path, `mb.fileTypeIcon`, `mb.fileCatalog`, `mb.directoryTotals` | A front-matter title needs the file’s own read, which this does not make |
| Prefetch | A tree row’s hover prefetch of a file’s body (`app.js`, 250 ms), the Commits panel’s speculative `prepareRevision`, `prefetchCounterpart` | All but `prefetchCounterpart` private; `app.js` has 75 bytes of startup budget |
| A link’s tooltip today | `WORKING_TREE_TITLE` as `data-tip-text` | The shell drops `data-tip-text` inside a `.metabrowser-kpress-host`, so it never shows in a rendered document, a pull request’s text, or a commit’s message; a trusted Markdown link keeps its author’s native `title` |

## Design

### The Rule for Tooltips on Links

`docs/design-system.md` gains **Tooltips on Links**, beside the tooltip sections, and
every link in the app follows it:

| Link | Tooltip |
| --- | --- |
| Opens a page in Metabrowser, in text whose words say nothing about what it opens (rendered Markdown, a pull request’s text, a Guided Review note, a commit’s message, a rendered diff) | The **link card**: what it opens, its title where known, and that it opens here |
| Leaves for another site, in the same texts | The link card’s one line saying where it goes, “Opens example.com in a new tab”, with “in a new tab” only where the link opens one |
| The app’s own chrome, whose text names what it opens (a Pulls row’s title, a crumb, a Files row) | None, as [Tooltips Add Information](../../../design-system.md#tooltips-add-information) already says |

The card is the app’s one tooltip, so it obeys every rule already there: shown on
pointer rest and never on focus, placed on its link and holding still, and put away by
the surface that drew the link (`hide(within)`). A link in a text the author titled
keeps that title, quoted as the author’s, in its card, and loses its native `title`, as
does an image inside it, whose title the card says where the link has none of its own;
an image fallback inside the link loses its own tooltip, whose address the card says
instead. So the reader never sees two tooltips.

An outside link has a card too, decided with the owner on 2026-11-26 after review: the
macOS app’s web view has no status bar, and `decorateExternalLink` marks only a GitHub
address, so a link to another site otherwise says nothing of where it goes.
Its card names the host as the URL parser reads it, and says “in a new tab” only where
the link has `target="_blank"`; an in-app card’s “Opens here in Metabrowser” reads
against it.

### The Card

One renderer draws every card, from data, so no surface can draw a card of its own.
It uses the tooltip’s existing content classes (`.tip-name`, `.tip-detail` in
`static/styles.css`), as a Files row’s tooltip does:

1. **What it is**, in `.tip-name`: the object’s mark and its identity: “Pull request
   #12”, “Stack #3”, “Commit a1b2c3d” (the shell’s short commit), the path of a file or
   folder, or “Pull requests”.
   A link to a tab or a changed file names it after the identity: “Pull request #12 ·
   Changes · docs/guide.md”.
2. **Its title**, when known and not already the link’s own text: a pull request’s
   title, a commit’s subject, a stack’s top member’s title, an author’s `title`. A pull
   request’s mark is its state icon only when its metadata says so: the address alone
   never establishes a state (External GitHub Links).
3. **Where it opens**, in `.tip-detail`: “Opens here in Metabrowser”, or, for a link to
   a branch that opens whatever is served, “Opens in the served working tree” on a
   folder’s page and “Opens at the served revision” on a pin’s or a mirror’s, which
   replace `WORKING_TREE_TITLE`. A commit the repository lacks says “Not in this
   repository” instead, and the card makes no fetch for it.
   No other card says its object is missing: a file’s or folder’s says where it opens
   whether or not a list the page holds names it, since none is every path a link can
   open (Data and Prefetch).

As built, a line that is the link’s own text, in any case and spacing, or a line above
it, is left out, the identity included, and the first line kept leads with the mark, so
a link whose text is its identity still shows its state.
An author’s title is its own line after the object’s title, and a provider’s `detail` a
`.tip-detail` line before where it opens.
The marks are the icon catalog’s: the pull request marks `decorateExternalLink` gives a
pull request’s address, the state’s from the github plugin’s `pullStateIcon`, loaded at
the first summary that gives a state; a stack’s `layers`; a file’s type from
`fileTypeIcon`; and none for a folder, which ends in `/`, or a commit, which is its ID.

### Data and Prefetch

A **link preview** is one kind’s answer for a resolved target:
`{kind, identity, title?, state?, detail?, missing?}`, each field plain text.
Providers return data, never HTML, and make only reads the app already makes for that
object, all cache-only.
The registry keeps no answer: each provider keeps what it reads for as long as that
stays true, reads again what failed or was not yet known, and says what it keeps at once
(`known`), so a card never says what the page knew once and no longer does.
What a provider keeps is bounded.

| Kind | Title from | Prefetch on rest |
| --- | --- | --- |
| Pull request, its tabs and files | `pulls?q=<n>`, kept by number for as long as the Pulls tab waits between its reads; a failed read, and a number a catalog not yet whole lacks, are read again | The github plugin’s page assets, and the record read with `warm=1`, which counts no view, once a page for each number |
| Stack | One read of the cache-only stacks route, reused for as long as the Pulls tab’s poller waits between its reads, a second while the snapshot is being refreshed; that poller is the plugin’s own and asks GitHub to refresh a snapshot that is due | The page’s assets |
| Commit | `MetabrowserGitPanel.commitSummary` and `keptCommitSummary`, which share `fetchCommitDetail`’s cache and its missing set, so the card follows what the panel keeps and clears | `MetabrowserGitPanel.prefetchCommit`: the detail first, then `prepareRevision(…, true)`, nothing for a commit the repository lacks, and never in place of a preparation still on its way |
| File or folder | The folder’s totals already known, read from the page each time and never kept; nothing for a file, whose type is its mark’s to say. No file is called missing: a served folder’s whole Quick File catalog leaves out hidden, gitignored, and symlinked files the folder still opens, and a pin’s lists only blobs, while its file route opens a folder or submodule a link names with no closing slash, so neither proves a path absent (`knownPath`) | `prefetchCounterpart` for its page; not its body (Follow-ups) |
| The pull request list | Static | The list view’s assets, `ensureKindAssets("pull-request-list")` |

A link starts its read and its prefetch once the pointer has rested on it for the tree’s
own hover delay, and asks the tooltip to show the card at once; the tooltip waits out
its appear delay, and a card whose title arrives in that time is shown with it (a `show`
still waiting takes the newer HTML and keeps its time, so the card appears on the appear
delay from the pointer’s arrival, as the golden’s timing shows).
A title that arrives later is its provider’s to keep, and the next rest’s card says it
from the pointer’s arrival.
At most one read and one prefetch are in flight; a newer rest waits for them rather than
aborting them, since an aborted request counts against the page’s `fetch_aborts` budget.

### Where It Lives

An on-demand module, `static/link-previews.js`, holds the registry, the delegated
pointer listener, the intent timer, and the renderer;
`static/link-preview-providers.js`, after it, registers one provider for each kind
(`provide(kind, {summary, known, prefetch})`). The two are the `link-previews` bundle,
which a page loads at its first pointer rest on a link a surface registered, and never
with the resolver (`repository-links`, now the GitPath codec and the resolver alone),
whose wait every surface’s first render shares.
A thin registration in the SDK’s view helpers (`previewLink`, `forgetPreview`, and
`disposePreviews` in `static/plugin-sdk-views.js`, the `sdk-views` bundle every view
already loads) keeps each link a surface registers, by identity, with one delegated
pointer listener per root, on every page, with or without a repository identity.
The first `pointerover` of a registered link from a pointer that is not a touch loads
the bundle; its registry then takes every registration, and the rest that load began, as
old as the load took (`rest`), so that rest’s card comes up for it; a press or a focus
during the load ends that rest.
From then on the SDK’s calls go straight to the registry.
A bundle that does not load leaves every link without a card and gives back the author’s
title the surface took off it, with one warning.
`enhance` and the Markdown enhancer register each link they make by identity, through
the SDK; the rendered diff registers its head links; a commit’s message on a page with
no resolver registers each of its links as the outside link it is.
Nothing is added to the startup scripts: a seam into the tree’s file prefetch does not
fit (Follow-ups).

As measured on 2026-11-27 (`server.py`, beside both bundles), the split took the
resolver’s wait from medians of 40 to 41 ms to 23 to 25 ms on loopback, and the first
rest on a fresh page, its bundle’s load included (20,039 bytes gzipped), comes up
medians of 314 to 331 ms after the pointer arrived, inside every rest’s window;
preloading the bundle in idle time brought that to 302 to 315 ms but costs every page
with a link the bundle, so a page loads it at the rest.

### API

- `window.MetabrowserLinkPreviews.register(root, anchor, target, mb, { authorTitle })`:
  called by the SDK’s `previewLink` for each link the resolver’s `enhance`, the Markdown
  enhancer, the rendered diff, and a commit’s message register; `target` is the
  resolver’s answer, a `view` or `route` target, a document’s own link’s `view` target,
  `{kind: "view-head", href}` for a rendered diff’s link to a file of its head, or
  `{kind: "external", url}` for a link to another site.
  A later call replaces the entry; a target the card says nothing of, such as a mail
  link’s, is dropped. It answers whether the link has a card.
- `window.MetabrowserLinkPreviews.rest(anchor, { elapsed, ended })`: the rest the SDK
  saw begin before the module loaded, *elapsed* ms ago, which the registry takes as its
  own: its card is asked for at once, and its summary and prefetch at the intent delay
  less *elapsed*; *ended* says a press or a focus ended it meanwhile.
- `window.MetabrowserLinkPreviews.forget(anchor)`: drops one link and puts its card
  away.
- `window.MetabrowserLinkPreviews.dispose(root)`: forgets a root’s links, stops
  listening to it, and puts its card away (`mb.tooltip.hide(root)`).
- `window.MetabrowserLinkPreviews.provide(kind, { summary, known, prefetch })`: a kind’s
  data, `summary(subject, { mb })` resolving to `{title?, state?, detail?, missing?}` or
  null, plain text only, which may read and answers what it keeps at once; an optional
  `known(subject, { mb })`, what it keeps now, with no read, for the card the pointer’s
  arrival asks for; and an optional `prefetch(subject, { mb })`. Nothing aborts a read,
  so a provider is given no signal.
- `window.MetabrowserLinkPreviews.subject(target, sourceKind?)`: what a target names,
  pure: `pull` (`number`, `tab`, `file`), `stack` (`number`, `file`), `commit`
  (`revision`), `file` or `folder` (`path`, `opens`, `target`), `pulls`, or `external`
  (`url`, `host`). A `/view/` path is read as the page’s source kind spells it,
  `mb.sourceKind()` when not given, since only that tells a pin’s GitPath wire from a
  folder’s name that looks like one.
  `path` is the display path the card shows, and `target` the navigation target as the
  address spelled it, the resolver’s own, or for a head link its wire path and decoded
  fragment, so a provider looks a file up and opens it by the resolver’s spelling.
- `window.MetabrowserLinkPreviews.card(subject, preview, { linkText, authorTitle, newTab })`:
  the one renderer, data in and escaped markup out; *newTab* is whether the link opens a
  new tab, which the registry reads from the link as the card is asked for.
- `window.MetabrowserLinkPreviews.INTENT_MS`: the intent delay, the tree’s
  `FILE_PREFETCH_HOVER_DELAY_MS`.
- A plugin reaches these through the SDK, never through the window global (AGENTS.md,
  Browser and Plugin Boundary):
  `metabrowser.previewLink(root, anchor, target, { authorTitle })`,
  `metabrowser.forgetPreview(anchor)`, and `metabrowser.disposePreviews(root)`, which
  keep each registration until the bundle loads
  ([docs/plugins.md](../../../plugins.md)). Before then `previewLink` answers whether
  the target is one a card is about, an in-app answer or an `http` or `https` address
  with a host, and the registry decides once it loads.
- `MetabrowserGitPanel.commitSummary(revision)`: the subject, author, time, and whether
  the repository has it, from the panel’s own cache, and
  `MetabrowserGitPanel.keptCommitSummary(revision)`: the same from what the panel holds
  now, with no read.
- `MetabrowserGitPanel.prefetchCommit(revision)`: the commit prepared as a hover on its
  row prepares it, for a rest on a link to it.

## Implementation Plan

### Phase 1: Link Previews

- [x] The design-system rule, the card, the registry, and the renderer, with a
  browserless session, a golden, and a parity row (`mb-wcya`)
- [x] The providers and prefetch for each kind (`mb-6wiy`)
- [x] Every surface registers its links: the resolver’s `enhance`, the Markdown
  enhancer, and the rendered diff; authored titles move into the card; the working-tree
  tooltip goes
- [x] A Chrome check of the card’s placement, delay, and content on a real page
- [x] The card in a bundle of its own, loaded at the first rest, and every link’s card
  on every page, with or without a GitHub identity (`mb-ezai`, review findings H3 and
  H9)

## Testing Strategy

Browserless sessions run the exact production modules, with a golden transcript and a
parity row for each new surface (AGENTS.md, CLI and Functional UI Parity); a Chrome
check confirms the tooltip’s placement and timing.
The renderer’s session holds one invariant per rule above: a card never repeats its
link’s text, never claims a state its data does not give, and never appears on focus.
Each of those sessions puts a stand-in at the boundaries it does not own, which is how
the review of 2026-11-26 found a card that came back after focus moved, an answer of
nothing kept for the page’s life, and an image’s tooltip fighting its link’s card, each
with every session green.
`tests/dom/link-card-integration-session.js` runs those boundaries for real, app.js’s
tooltip and its delegated listeners, the resolver, the SDK’s registration, the registry,
and the providers on recorded answers, with a golden and a parity row of its own.
`tests/dom/link-preview-loader-session.js`, with its own golden and parity row, runs the
SDK’s registration whole on pages with no GitHub identity and one with: registration
before the bundle, the first rest loading it and keeping its time, a rest the pointer
left or a press ended during the load, a link forgotten or a document disposed before
it, a load that fails, and a touch.

The Chrome check is `tests/test_link_card_chrome.py`, which drives
`tests/dom/link-card-chrome.mjs`. It serves the GitHub stand-in’s checkout, whose
catalog holds pull request 8, with a document that links a file with its author’s title,
a folder, #8 by its number and again by its title, the head commit, the list of pull
requests, and an outside page, then, past a screenful of words, the file again and the
README. Once the catalog holds #8, Chrome’s own pointer (`Input.dispatchMouseEvent`)
rests twice on each in-app link, on empty space between until the tooltip’s fade has
ended, and the check holds:

- **Delay.** The time from the pointer’s arrival to the card’s appearance, in the page’s
  clock, printed for each rest, falls in a window of `INTENT_MS` and
  `TOOLTIP_APPEAR_DELAY`, both read from the page: from the appear delay to their sum,
  on every rest, whether its provider answers at once (a file, a folder, the list),
  reads the server (#8, the commit), or the page already knows its card.
  A rest whose card started its delay again at the intent delay would come at their sum
  or later.
- **Content.** The card’s `.tip-name` names what the link opens (the path its address
  opens, “Pull request #8”, or the commit’s short ID), its last line is “Opens here in
  Metabrowser”, and no line is the link’s words; by the second rest it says #8’s title
  from the catalog with its merged mark, the commit’s subject, and the author’s title,
  and the link whose words are #8’s title leaves it out.
- **Placement.** The card is centered below its link, or above it at the pane’s foot,
  and its box and markup are the same after the pointer moves within the link.
- **Input.** Moving away puts the card away as the pointer leaves; an outside link shows
  none; Shift-Tab with a card up puts it away; focus brought by Tab and Shift-Tab onto
  each link shows none.
- **The page.** No link with a card carries a native `title`, before or after the rests,
  and nothing was thrown, logged as an error, or failed to load, but Chrome’s own
  `/favicon.ico`, as the page names no icon
  ([Known Departures](../../../design-system-icons.md#known-departures)).

A last step moves the pointer in one step from the file’s link, with its card up, onto
the README beside it, within the fade, and checks that the README’s card comes up on the
README’s link in the same window.
Before the fix in `static/app.js` (`tooltipShown`), the file’s card came up again, on
the file’s link, when the README’s card was asked for at the intent delay, and stayed
while the pointer rested on the README (the shell’s bug H1); `KNOWN_BUG_H1` in the
session, now false, would turn the step back into a record of what shows.

With the renderer’s “Opens here in Metabrowser” line dropped, or `register` made a
no-op, it fails on every rest.

On that page and on a second, a plain folder with no GitHub identity whose document
links another file, with its author’s title, and another site, the check also holds that
the card’s bundle is not asked for before a rest, that the first rest on a file’s link
of the fresh page, cache off, loads it and shows the card in every rest’s window moved
by the time the load took, which it prints; on the plain folder’s page, that both links
have their cards and that the resolver is never asked for.

### Decisions in the Split (`mb-ezai`, 2026-11-27)

The coordinator’s design for findings H3 and H9 was built as written, with these choices
recorded:

- **The resolver’s delegates are gone.** `previewLink`, `forgetPreview`, and
  `disposePreviews` left `MetabrowserRepositoryLinks`; every surface calls the SDK’s,
  and `enhance` registers through the SDK it is given.
  Keeping both would have been two ways to one registry, and the delegates were
  unreleased.
- **The SDK’s answer before the bundle loads is a reading, not the registry’s.**
  `namesLinkCard` accepts an in-app answer and an `http` or `https` address with a host,
  so a mail link keeps its title; the registry’s `subject` decides at the hand-over, and
  a link it turns down gets back the title the surface took.
  Moving `subject` into the SDK would have made the answer exact at about 2 KB more on
  every view’s critical path, for links no surface draws.
- **The first rest keeps its time but not its appear delay.** The registry’s `rest` asks
  for the summary when a rest that began on a loaded page would, and the tooltip waits
  its whole appear delay from the hand-over, since `showTooltip` in `static/app.js`, a
  startup script at its budget, takes no earlier start.
- **No preload.** Measured, it brought the first card’s medians 0 to 28 ms sooner and
  cost every page with a link the bundle.
- **A commit’s message with no resolver registers its links as outside links**, which
  they are there. A pull request’s and a stack’s pages exist only with a GitHub identity,
  and keep registering through the resolver alone; their texts are read again when a
  late resolver arrives.
- **The rendered diff’s SDK narrows to what `enhance` reads** (`repositoryLinksSdk` in
  `builtin_plugins/diff/diff-view.js`), since the registry now draws with the page’s
  SDK, not the surface’s.

## Open Questions

- None: the owner’s request settles what the card says and where it appears.

## Follow-ups

- **A file’s body on a rest.** The tree’s hover prefetch (`startHoverPrefetch` in
  `static/app.js`) is the only reader of a file’s body ahead of a click, and `app.js` is
  a startup script. On 2026-11-26 the startup scripts were 75 bytes under their budget
  (`devtools/check_startup_scripts.py`), and the smallest seam, a shell method that sets
  the tree’s prefetch path and calls `startHoverPrefetch` for a name that is not
  `.jsonl`, cost 67 of them.
  That seam is not enough: it shares the tree’s one abortable slot, so the next tree
  hover would abort the link’s read, and it has no size bound, which the tree takes from
  the row’s own size, and a link’s file may have no row.
  A seam with its own slot and a size bound of its own does not fit, so a rest on a link
  does not read the body until the startup scripts have room, or the tree’s prefetch
  moves out of them.

## References

- [In-App Link Resolution](plan-2026-11-26-in-app-link-resolution.md)
- [Design System: tooltips](../../../design-system.md#one-tooltip-and-it-is-ours)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
