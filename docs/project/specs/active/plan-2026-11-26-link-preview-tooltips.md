# Feature: Link Preview Tooltips

**Date:** 2026-11-26 (last updated 2026-11-26)

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
| Leaves for another site | None: the [External GitHub Links](../../../design-system.md#external-github-links) mark says it leaves, and the browser shows the address |
| The app’s own chrome, whose text names what it opens (a Pulls row’s title, a crumb, a Files row) | None, as [Tooltips Add Information](../../../design-system.md#tooltips-add-information) already says |

The card is the app’s one tooltip, so it obeys every rule already there: shown on
pointer rest and never on focus, placed on its link and holding still, and put away by
the surface that drew the link (`hide(within)`). A link in a text the author titled
keeps that title as the card’s description, and loses its native `title`, so the reader
never sees two tooltips.

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
   a branch that opens whatever is served, “Opens in the served working tree”, which
   replaces `WORKING_TREE_TITLE`. A commit the repository lacks says “Not in this
   repository” instead, and the card makes no fetch for it.

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
object, all cache-only:

| Kind | Title from | Prefetch on rest |
| --- | --- | --- |
| Pull request, its tabs and files | `pulls?q=<n>`, cached per page by number | The github plugin’s page assets, and the record read with `warm=1`, which counts no view, once a page for each number |
| Stack | One read of the cache-only stacks route, reused for as long as the Pulls tab’s poller waits between its reads; that poller is the plugin’s own and asks GitHub to refresh a snapshot that is due | The page’s assets |
| Commit | `MetabrowserGitPanel.commitSummary`, which shares `fetchCommitDetail`’s cache and its missing set | `MetabrowserGitPanel.prefetchCommit`: the detail first, then `prepareRevision(…, true)`, nothing for a commit the repository lacks, and never in place of a preparation still on its way |
| File or folder | Its type’s name, whether a complete file catalog holds a file, and the folder’s totals already known | `prefetchCounterpart` for its page; not its body (Follow-ups) |
| The pull request list | Static | The list view’s assets, `ensureKindAssets("pull-request-list")` |

A link starts its read and its prefetch once the pointer has rested on it for the tree’s
own hover delay, and asks the tooltip to show the card at once; the tooltip waits out
its appear delay, and a card whose title arrives in that time is shown with it (a `show`
still waiting takes the newer HTML and keeps its time, so the card appears on the appear
delay from the pointer’s arrival, as the golden’s timing shows).
A title that arrives later is cached for the next rest.
At most one read and one prefetch are in flight; a newer rest waits for them rather than
aborting them, since an aborted request counts against the page’s `fetch_aborts` budget.

### Where It Lives

A new on-demand module, `static/link-previews.js`, in the `repository-links` bundle the
resolver already loads, holds the registry, the delegated pointer listener, the intent
timer, and the renderer; `static/link-preview-providers.js`, after it in the bundle,
registers one provider for each kind (`provide(kind, {summary, prefetch})`). `enhance`
and the Markdown enhancer register each in-app link they make by identity; the rendered
diff registers its head links.
Nothing is added to the startup scripts: a seam into the tree’s file prefetch does not
fit (Follow-ups).

### API

- `window.MetabrowserLinkPreviews.register(root, anchor, target, mb, { authorTitle })`:
  called by the resolver’s `enhance`, the Markdown enhancer, and the rendered diff for
  each in-app link; `target` is the resolver’s answer, a `view` or `route` target, or
  `{kind: "view-head", href}` for a rendered diff’s link to a file of its head.
  A later call replaces the entry; a link the resolver leaves as written is dropped.
  It answers whether the link has a card.
- `window.MetabrowserLinkPreviews.forget(anchor)`: drops one link and puts its card
  away.
- `window.MetabrowserLinkPreviews.dispose(root)`: forgets a root’s links, stops
  listening to it, and puts its card away (`mb.tooltip.hide(root)`).
- `window.MetabrowserLinkPreviews.provide(kind, { summary, prefetch })`: a kind’s data,
  `summary(subject, { mb, signal })` resolving to `{title?, state?, detail?, missing?}`
  or null, plain text only, and an optional `prefetch(subject, { mb })`. The signal is
  never aborted.
- `window.MetabrowserLinkPreviews.subject(target, sourceKind?)`: what a target names,
  pure: `pull` (`number`, `tab`, `file`), `stack` (`number`, `file`), `commit`
  (`revision`), `file` or `folder` (`path`, `opens`, `target`), or `pulls`. A `/view/`
  path is read as the page’s source kind spells it, `mb.sourceKind()` when not given,
  since only that tells a pin’s GitPath wire from a folder’s name that looks like one.
  `path` is the display path the card shows, and `target` the navigation target as the
  address spelled it, the resolver’s own, or for a head link its wire path and decoded
  fragment, so a provider looks a file up and opens it by the resolver’s spelling.
- `window.MetabrowserLinkPreviews.card(subject, preview, { linkText, authorTitle })`:
  the one renderer, data in and escaped markup out.
- `window.MetabrowserLinkPreviews.INTENT_MS`: the intent delay, the tree’s
  `FILE_PREFETCH_HOVER_DELAY_MS`.
- A plugin reaches these through the resolver’s runtime, which
  `metabrowser.loadRepositoryLinks()` already gives it, and never through the window
  global (AGENTS.md, Browser and Plugin Boundary): `previewLink`, `forgetPreview`, and
  `disposePreviews`, each a no-op where the cards are not loaded
  ([docs/plugins.md](../../../plugins.md)).
- `MetabrowserGitPanel.commitSummary(revision, {signal})`: the subject, author, time,
  and whether the repository has it, from the panel’s own cache.
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

## Testing Strategy

Browserless sessions run the exact production modules, with a golden transcript and a
parity row for each new surface (AGENTS.md, CLI and Functional UI Parity); a Chrome
check confirms the tooltip’s placement and timing.
The renderer’s session holds one invariant per rule above: a card never repeats its
link’s text, never claims a state its data does not give, and never appears on focus.

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
