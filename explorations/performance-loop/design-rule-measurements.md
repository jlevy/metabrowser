# Design Rule Measurements

Measurements taken once, in a real engine, to decide a rule in the
[design system](../../docs/design-system.md).
Each section names the rule it set; the rule itself lives in the design system, and a
bound’s own measurement lives beside its constant.
These are records: they keep the date, the engine, and what was compared, and they are
not rewritten when the code moves on.
Rerun one before changing the rule it supports.

## Page Headers

For [Page Headers](../../docs/design-system.md#page-headers) and
[Actor Identity](../../docs/design-system.md#actor-identity), recorded on 2026-11-16,
when every line under a commit’s and a pull request’s titles took the body size and the
commit’s page took a pull request’s order (mb-26zj): measured in headless Chrome 152 at
980, 560, and 360 px by `tests/test_page_header_chrome.py`, every line and every run of
text under both titles is 14 px, but chips and the 13 px revision; both titles are 24 px
on 30 px lines, two lines tall; every line is 6 px under the one before; and both
authors’ 18 px boxes start on the header’s content edge, both names 22 px in.
The commit’s author, revision, and age lines are 21 px each, and its Diff summary 24 px
at 560 px and wider and 40 px at 360 px, where it wraps; a pull request’s row of ages
and status line are 21 px, and its header is 235 px with no labels and 261 px with them.
Before, at 760 px, the Diff summary was 13 px on both pages, a pull request’s row of
ages and status line were 12 px and 18 px tall, its header 229 and 255 px, and the
commit’s metadata one line 8 px under its subject.

## Type by Role

For [Type Scale](../../docs/design-system.md#type-scale), recorded on 2026-11-16, when
secondary metadata took the size of the text it accompanies (mb-ctlu): an inventory of
every visible run of text, read in headless Chrome 152 on a Mac in a 1280 by 900 window,
light theme, on the Pulls, Files, and Commits panels, a Pulls row opened, a pull
request’s Conversation, Changes, and Checks, the Diff summary opened, a file view of
each built-in plugin’s kind, a folder’s Overview and Treemap, a commit’s page and hover
card, tooltips, the settings menu, the ref selector, the Files type menu, Help, and
Quick Search, served from the GitHub stand-in (`tests/github_pull_fixture.py --serve 7`)
and `tests/manual-fixtures`. Size and line height, in px, before and after; nothing else
changed between the two runs.

| Text | Before | After |
| --- | --- | --- |
| A tree row’s size and age, beside its 13 / 19.5 name | 12 / 18 | 13 / 19.5 |
| A Pulls row’s age, and its second line’s author beside the 13 px number | 12 / 18 | 13 / 19.5 |
| A Commits row’s author and age, and the Commits tally’s age inside its 13 px line | 12 / 18 | 13 / 19.5 |
| The navigation column’s freshness line, “Fetched just now” | 12 / 14.4 | 13 / 15.6 |
| A changed-files tree’s line counts, beside 13 px names | 12 / 18 | 13 / 19.5 |
| A file’s and a folder’s header: its path | 13 / 19.5 | 14 / 21 |
| A file’s and a folder’s header: size, count, age, and mirror note | 12 / 18 | 14 / 21 |
| A diff file bar: its path, change letter, line counts, and View file | 13 / 19.5 | 14 / 21 |
| A pull request’s Checks summary and each check | 12 / 18 | 14 / 21 |
| A review comment’s file, in its 14 px card head | 13 / 19.5 | 14 / 21 |
| A tooltip’s detail lines, under its 14 px text | 12 / 16.8 | 14 / 19.6 |
| Help’s descriptions and group context, Quick Search’s status | 12 / 18 | 13 / 19.5 |
| “Updated just now” and the navigation metadata line | 13 / 19.5 | 13 / 19.5 |
| A pull request’s header lines, its status line among them | 14 / 21 | 14 / 21 |

Chips, badges, buttons, menus, keycaps, labels, monospace, and titles read the same in
both runs: controls 12 px, ref chips 0.9 of their text, labels 12 px in caps, section
headings 14 px in caps, code 12 / 18, a revision 13 px, titles 24 / 30.

No list’s row height moved, at panes of 300 and 180 px: a tree row 24 px, a Commits row
22 px, and a Pulls row 43 px.
The column’s foot is 30 px at 300 px; at 180 px, where it wraps, it grew 2.2 px, from
45.8 to 48 px, and no list’s row constant depends on it.
At the 180 px pane, the Commits row’s meta column clipped its age by 9.6 px at 12 px and
by 14.2 px at 13 px; with the author ellipsizing first, the age is whole.
The Pulls window’s estimate for an unmeasured row is 41.5 px against the 43 px it
measures, before and after.
`tests/test_type_scale_chrome.py`, run against the stylesheets as they were, failed 27
of its checks, every role this changed.

On 2026-11-17 a file’s or a folder’s header and a diff file bar took the main view’s 14
px, by the owner’s rule that the navigation column is the one region set a step under
the body size; the navigation column’s own header path stays 13 px.
Measured again in headless Chrome 152 at a device pixel ratio of 1, against the same at
13 px:

- The header row stays 41 px.
  On a 900 px window showing `root / src / metabrowser / color_oklch.py`, the largest
  width a crumb gave up was 0.219 px at a root shrink weight of 1000, 0.047 px at 5000,
  0.016 px at 20000, and none at 100000; at 13 px in the same run they were 0.188,
  0.031, 0.016, and 0 px.
  This run recorded the widths, not whether a crumb showed an ellipsis; the stylesheet’s
  comment keeps the first 13 px run’s widths, 0.164, 0.031, 0.008, and 0 px, with what
  each showed. The root had nothing left to give below a 367 px header, against 351 px at
  13 px, and at every header from 249 to 689 px a filename cut short ended in an
  ellipsis with the copy control inside the box.
- With a mirror named `metabrowser-v012-landing-docs`, at 12 header widths from 240 to
  1340 px the root measured what it did with the note removed, the note was whole or
  absent, and where it showed its text box shared the path’s top.
  14 em is 196 px against the 189.9 px of `mirror in ~/.metabrowser/cache/`.
- A diff file bar is 24 px, and 29 px with the Markdown chooser, at both sizes, and an
  empty bar, which the diff view measures to reserve one, is 24 px at both.
- View file’s two forms were measured in headless Chrome 153 on a commit’s page, with
  the two controls the diff view writes placed in each bar where it places them, since a
  served checkout draws none, and each baseline read as the top of a zero-size inline
  block on it. At device pixel ratios of 1 and 2, the button form sat on the path’s
  baseline at 14 and at 13 px, and the link form sat above it, by 0.5 px at 14 px and
  0.75 px at 13 px. The link took the bar’s 1.5 line height, 21 px, where the toggle and
  the button take a button’s `normal`, 20 px.
  With the link at `normal` too, both forms sit on the path’s baseline at both sizes and
  both ratios, and the bar stays 24 px.
- In a Pulls row, “12mo”, the longest compact age, is 31.1 px of its 32.3 px column at
  13 px. WebKit was not measured.

## Row Baselines

For
[Row Text Shares a Baseline](../../docs/design-system.md#row-text-shares-a-baseline):

- The diff file bar’s View file controls, set at `--ui-small-font-size` beside the path,
  sat off the path’s baseline, a link by 0.75px and a button by 0.5px, measured in
  Chromium at a device pixel ratio of 2. Set at the path’s own size and line height,
  they center onto one baseline.
  At the path’s size alone the link form still sat 0.5 px above it at 14 px and 0.75 px
  at 13 px, at ratios of 1 and 2, until it took the toggle’s `normal` line height
  ([Type by Role](#type-by-role)).
- A mirror’s location note at the far end of the file header, centered rather than
  baseline-aligned, sits 0.25px above the path at a device pixel ratio of 1. On
  2026-11-16 and 2026-11-17, at the header’s one size, 13 px and then 14 px
  ([Type by Role](#type-by-role)), its text box, the path’s, and the size’s share one
  top at a device pixel ratio of 1.
- Aligning the Git commit summary’s monospace revision on one baseline with the
  body-size sans beside it grows that line by 1.25px at a device pixel ratio of 2, so it
  stays centered.

## Disclosure Motion

For [Disclosure Motion](../../docs/design-system.md#disclosure-motion): a deep reveal
that navigation opened with the travelling animation moved the rows below it 43 to 131
px a frame with no input, which is why such a reveal lands in place with
`.tree-children-instant`.

## Disclosure Toggle Selection

For
[Disclosure Toggles Never Select Text](../../docs/design-system.md#disclosure-toggles-never-select-text).
Without the rule, a triple click on a rendered Markdown diff’s **5 unchanged blocks**
fold selected its label and every paragraph it revealed, in Chrome; in WebKit, a double
click on a folder row selected the folder’s name, because WebKit reads only the prefixed
`-webkit-user-select` and the tree rows had only the unprefixed rule.

Measured on 2026-11-13 with real double and triple clicks, in headless Chrome on a
folder row’s name, padding, and size and on the fold’s label and padding, and in a
`WKWebView` on a folder row’s name and a section trigger: with the rule, nothing was
selected, and a `mousedown` handler that prevented the default of the second and third
presses changed nothing in either engine, so the app has none.

## Branch Chip Sizes

For [Branch Chips](../../docs/design-system.md#one-ratio), measured in Chrome, light
theme: the text each context sets, the chip it gets at `--git-ref-font-scale`, and the
fixed chip size the ratio replaced.

| Context | Text around the chip | Chip | Fixed chip |
| --- | --- | --- | --- |
| A Git history row | 13px subject | 11.7px | 12px |
| A commit’s summary and its tooltip | 14px metadata | 12.6px | 12px |
| A pull request’s header | 14px branch line | 12.6px | 12px |
| The ref selector’s button and list | 12px | 10.8px | 12px |

## Short Commit IDs

For [Short Commit IDs](../../docs/design-system.md#short-commit-ids), recorded on
2026-11-19 (mb-qq4e), when an ID took its line’s size with its monospace face scaled to
the sans’s x-height, in place of `--nav-font-size` and the ref selector’s chip ratio.
Measured in headless Chrome 152 on macOS 26.5 against a served mirror of a public
repository and a revision of a local checkout, in both font sets.

The faces’ x-heights per em, at 12, 13, and 14 px, by the `ex` unit and by the ink of
“x” on a canvas, which agreed: Source Sans 3 (Clean Fonts) 0.486; system-ui (System
Fonts), SF Pro at its text optical size, 0.526, and 0.508 at 100 px and above; Menlo,
which Chrome draws for the monospace stack since it cannot reach SF Mono by name, 0.547,
the same as its OS/2 table.
SF Mono, which WebKit draws, is 0.526 in its OS/2 table (1077 of 2048 units); it was not
measured in the macOS app.
Chrome reported the faces it drew through `CSS.getPlatformFontsForNode`.

The x-height of an ID and of the line around it, in px.
Before is the ID’s computed size times Menlo’s measured ratio, and on a checkout’s
heading the old rule put back in the page; after is the width of `100ex` in each, over
100\. A heading’s line figure is 13 px times the regular sans’s ratio, since its sans is
the bold name, whose x-height measured 6.45 in Clean and 6.99 in System.

| Context, line size | Font set | Before: ID / line | After: ID / line |
| --- | --- | --- | --- |
| A checkout’s revision’s heading, 13 px | Clean | 7.109 / 6.32 (+12.5%) | 6.316 / 6.32 |
| A checkout’s revision’s heading, 13 px | System | 7.109 / 6.84 (+3.9%) | 6.836 / 6.84 |
| A commit’s page and hover card, 14 px | Clean | 7.11 / 6.80 (+4.5%) | 6.803 / 6.805 |
| A commit’s page and hover card, 14 px | System | 7.11 / 7.37 (−3.5%) | 7.361 / 7.369 |
| The ref selector’s rows, 12 px | Clean | 5.91 / 5.83 (+1.2%) | 5.830 / 5.833 |
| The ref selector’s rows, 12 px | System | 5.91 / 6.32 (−6.5%) | 6.311 / 6.316 |

With the line’s ratio inherited, an ID’s line box was a whole 21 px line around 15 px of
glyphs, whose half-leading put its top above the sans’s, and a Conversation commit row,
which aligns its items on their baselines, was 22 px, so two commits’ glyphs stood 22 px
apart against the 20 px rhythm; with `line-height: normal` on the ID the row is 21 px
and the rhythm holds.
In Clean Fonts the old ID made a checkout’s revision’s heading 24.5 px tall, and it is
23.5 px now, as in System Fonts.
No ref selector row or commit page line changed height.
A served mirror’s heading has no ID now.
WebKit honored `font-size-adjust` on a span in a QuickLook render of a static page.

## Regions That Moved

For [Regions Keep Their Boxes](../../docs/design-system.md#regions-keep-their-boxes):
before each region kept its slot, chrome that came and went moved more than content did.
The filter bar moved the content 37 px on every main-tab switch, the view tab bar 30 px
between files, a scrollbar 11 px, and the Commits tab 78 px on every landing.

## A Repaint Keeps Its Images

For
[A Repaint Keeps Its Images](../../docs/design-system.md#a-repaint-keeps-its-images).

### A Rebuilt Avatar

Measured in the app’s WKWebView (WebKit 21624, macOS 26.5) on 2026-11-13, when the pull
request header built its actor on every tab switch, with the avatar served locally after
80 ms, by reading the header’s avatar at each animation frame and counting requests at
the server: on each of 9 tab switches the rebuilt lazy avatar was requested again, and
its `complete` was false and its `naturalWidth` 0 for 3 frames, 100 ms at that window’s
30 frames a second.
Eager, it made no request, and `complete` and `naturalWidth` were set
in its first frame on all 9. That the eager avatar then paints in that frame is an
inference: a page cannot read WebKit’s decoding or paint.
Pixels were read only in headless Chrome 152, whose screencast showed no blank avatar
frame in 9 switches either way; Chrome had the lazy image complete in its first frame
too, so the blank was WebKit’s.

### A Node Replaced Under the Pointer

Measured in headless Chrome 152 on 2026-11-13, with the pointer resting on the header’s
head branch chip while the page switched tabs: when the header built its parts again,
the new chip was not hovered and its copy button was hidden in the task that replaced
it, and read at the next animation frame Chrome had hovered it again and fired
`mouseenter` on it again.
That no frame painted the button hidden is an inference from those readings.
That `mouseenter` gives the shell’s tooltip a new anchor and restarts its delay
(`showTooltip` in `static/app.js`). Keyboard focus on the chip’s copy button went to the
document body on each tab switch.
With the header keeping its parts, the chip is the same node, no `mouseenter` fires, and
the focus stays. WebKit’s hover after such a replacement was not measured.

### A Re-entered Markdown Document

Measured in the same WKWebView on 2026-11-13, on a document with three images in its
first screen and one 4,800 px down, served by Metabrowser behind a proxy that delayed
each image 80 ms and counted requests, and reading each of the three at each animation
frame and again after layout.
Leaving for another file and coming back, each of 5 returns asked for all three images
again and left each without its image for 3 frames, 100 ms at 30 frames a second.
With the held images eager, the returns asked for none, and each image was complete,
with its width, in its first frame.
Making the shown images eager in the first frame, after they had been created lazy,
changed nothing: each return still asked for all three, and each was blank for 3 or 4
frames. So WebKit had given up the copy when it deferred them, an inference from the
counts. Without removing the authored address first, each return also asked the server
for the three images at their authored addresses.
Switching to Source and back built nothing, before and after: no request and no blank
frame. Headless Chrome 152 asked for nothing and had every image complete in its first
frame, before and after, and neither engine asked for the image far down.

### Versioned Addresses

Measured again on 2026-11-14, in the same WKWebView (WebKit 21624.2.5.11.8, macOS
26.5.2) and in headless Chrome 152, against the code before versions (7e27e32b), with
the same document and an image from another origin added to its first screen, served
with `max-age=300` and delayed 80 ms like the rest.
Each return was read the same way, and the replaced image, 240 by 120 and red, became
360 by 90 and magenta at the same path, told apart by its natural size and by a pixel
drawn from it:

| Engine | Code | 5 returns, nothing changed | Return after editing the document | Return after replacing the image | Reload after that |
| --- | --- | --- | --- | --- | --- |
| WKWebView | before | served images: no request, no blank frame; outside image: asked again each time, 3 or 4 blank frames | asked again, 3 blank frames | asked again, 3 blank frames, new image | new image |
| WKWebView | versions | no request, no blank frame, outside image included | no request, no blank frame | asked at its new address, 3 or 4 blank frames, new image | new image |
| Chrome 152 | before | no request, no blank frame | no request | no request, old image | asked again, new image |
| Chrome 152 | versions | no request, no blank frame | no request | asked at its new address, 6 blank frames at 60 a second, new image | no request, new image |

Before versions, Chrome showed the old image on the return without asking, because it
reuses an image the page has loaded at the same address whatever its headers say; its
reload asked again because `/raw` was `no-cache`. With versions, a change to the
document costs its images no round trip in WebKit, since nothing forgets them, and a
replaced image is asked for once, at its new address, in both engines.
After the reload Chrome kept the new image from its cache without asking, the PNG’s
answer at the current version being kept for a year; WebKit asked for it again.
With an SVG added to the first screen, whose answer is revalidated, and an image from
another origin at a scheme-relative address, each of 5 returns in WKWebView asked for
neither and had both complete in their first frame, as Chrome did for the SVG.

## Git Commit Summary

For [Git Commit Summary](../../docs/design-system.md#git-commit-summary), recorded on
2026-11-15, when the Diff summary took the place of the commit’s change counts: measured
in Chrome 152 at 980 to 320 px, the summary sits 6 px under the identity and 16 px over
the description, its place on the subject’s edge and its toggle hung 4 px into the
gutter; its header is one 24 px row at 560 px and wider and wraps to two lines at 420 px
and three at 320 px, all before the page is shown; opened, its tree is under it and
above the description; with no diff the totals line is one row under the identity; and
an empty place takes no room.

Measured again on 2026-11-16 in Chrome 152 at 980 to 320 px, when the summary’s statuses
became Git’s letters: the summary sits where it did, and for “35 files changed · 2 A, 3
D, 30 M · +1,234 −3,423” its header is one 24 px row at 420 px and wider and wraps to
two lines at 320 px, breaking after a dot, all before the page is shown.

Measured again on 2026-11-16 in Chrome 152, when its lines took a pull request’s order
and the body size (mb-26zj): the summary sits 6 px under the age line and 16 px over the
description, and its header is one 24 px row from a 373 px pane, where it was from 354
px at 13 px, and wraps to two lines at 320 px.

## Diff Summary

For [Diff Summary](../../docs/design-system.md#diff-summary).

### Its First Level

Recorded on 2026-11-15, when the tree’s first level moved one indentation step in from
its header: before, a diff’s toolbar started the first level 4 px in from the header.

### The Pending Placeholder

Recorded on 2026-11-16, when a pull request header’s Diff summary row took the pending
placeholder: measured in Chrome 152 at 560, 420, and 360 px in both themes, the block is
221 by 11.05 px, at the row’s start and centred on its line, the row is 24 px before and
after the summary arrives, and the tab bar under it does not move.

Recorded again on 2026-11-16, when the summary’s statuses became Git’s letters: measured
in Chrome 152 at 560, 420, and 360 px in both themes, the block is 188.5 by 11.05 px
(14.5 em of the header’s type), at the row’s start and centred on its line, the row is
24 px before and after the summary arrives, and the tab bar under it does not move.
A summary of one status, from “1 file changed · 1 M · +3 −1” to “8 files changed · 8 M ·
+120 −30”, ends 13.88 to 15.88 em from the row’s start, its text 13.42 to 15.42 em, and
the block ends between the two; one of three statuses, “35 files changed · 2 A, 3 D, 30
M · +1,234 −3,423”, ends its text at 22.18 em.

Recorded again on 2026-11-16, when each status count’s letter became bold with its
number: measured in headless Chrome 152 at 560 px in both themes, in the header’s
navigation size, a summary of one status ends 13.91 to 15.92 em from the row’s start,
its text 13.45 to 15.46 em, 0.03 to 0.04 em later than before, and the 14.5 em block
still ends between the two; one of three statuses ends its text at 22.26 em, 0.08 em
later.

Recorded again on 2026-11-16, when the summary’s header took the body size (mb-26zj):
the block is 203 by 11.89 px, still 14.5 em of the header’s type, now 14 px.

Recorded on 2026-11-17, when the placeholder began at a page’s first paint rather than
at its core preview (mb-30dz): headless Chrome 152, this repository served as a checkout
on a copy of an everyday cache, three back-to-back pairs a case at a load average of 16
to 41, each frame’s row read from navigation start, or from the click.
A direct link to #470, its record not cached: the header was in sight with an empty row
for 1455 to 1886 ms, the placeholder showed at 1822 to 2286 ms; after, the row was never
seen empty and the placeholder showed at 286 to 315 ms, with the header.
A Pulls row of #521, its record not cached, clicked: empty for 993 to 1268 ms, the
placeholder at 1074 to 1419 ms; after, never empty, the placeholder at 67 to 87 ms.
#502, cached, on a server’s first visit: empty for 517 to 596 ms, the placeholder at 849
to 959 ms; after, never empty, at 295 to 330 ms.
The summary arrived as before in each case, 2.7 to 4.8 s cold and 1.1 to 1.3 s warm.

### The Cached Brief Line

Recorded on 2026-11-17, when a pull request header’s Diff summary row began holding the
cached changed-files list’s brief line while its comparison is read (mb-z8ea): measured
in headless Chrome 152 at 560, 420, and 360 px in both themes by
`tests/test_github_pull_header_chrome.py` (`summary-wait`), the brief line of “35 files
changed · 2 A, 3 D, 30 M · +1,234 −3,423” has its words 16 px from the content edge and
2 px under the row’s top, and its text ends 308.19 px from the content edge at 560 and
420 px and 291 px at 360 px, where it is cut short, each the same as the summary that
replaces it; the row is 24 px before and after, and the tab bar does not move.
Without the toggle’s right padding the line cut short ended 6 px later, and without a
button’s `normal` line its words were 0.5 px higher.
On this repository served as a checkout, at a load average of 38 to 94, three runs a
case: opened from a Pulls row, the line showed 110 and 151 ms after the click, read from
the row’s line with no request (in the third run the row’s list was of another head, and
the placeholder held the row), and the summary at 3.2 to 4.4 s; a direct link to #470,
its record not cached, showed it at 1.3 to 2.2 s (before the line waited for a known
head, which the core brings at about the same time), its read 0.66 to 1.27 s on a server
just started, and the summary at 4.5 to 6.4 s.

### A Kept Comparison

Recorded on 2026-11-16, when a pull request’s page began keeping the comparisons it read
for the document (`createComparisonKeep`, whose comment has the same readings).
Before, every visit read the comparison again once the browser was idle, and a page is
not idle while it draws its record: measured in headless Chrome 152 on the GitHub
stand-in at a load average of 9 to 12, moving between pull requests of 26 to 121 files
from the Pulls tab, a revisit’s summary arrived 22 to 50 ms after the click, and 175 to
238 ms at four times slower CPU, most of it the wait for idle; with no
`requestIdleCallback`, where the wait is for 250 ms with no input after a press, a
revisit’s arrived 253 to 256 ms after it.
With the keep, measured again after review at a load average of 19 to 47, a revisit’s
summary arrived with its record: 16 to 27 ms after the click, 46 to 63 ms at four times
slower CPU, and 16 to 23 ms with no `requestIdleCallback`, a pull request first opened
on Changes included; and a first visit to a row the pointer rested on for 250 ms, 9 to
12 ms after the click, where it was 283 to 343 ms.

### A Pulls Row’s Change Line

Recorded on 2026-11-17, when the Pulls tab’s prefetch began listing changed files from
the store before it reads records (`_prepare_lists` in
`src/metabrowser/builtin_plugins/github/pull_prefetch.py`, whose docstring has the same
readings). Measured in headless Chrome 152 on this repository’s own Pulls tab, served
from its checkout with a fresh cache, 11 open rows in view, at a load average of 11 to
14; the list of pull requests was drawn 6.4 s after the tab opened in both.
Before, the lane took turns, a record of 3.6 to 4.7 s and then a list from GitHub of 0.3
to 2 s, and the rows’ change lines were drawn from 12.3 s to 40.6 s. After, every list
is the store’s comparison of the row’s head with the mirror’s base branch, with no
GitHub request: the lines were drawn from 9.4 s to 10.4 s, of which attaching the
checkout’s store took 2.3 to 2.5 s once, 11 merge bases 0.42 s, and each list 42 to 134
ms. A batch of heads the store lacks is one Git fetch: 39 of this repository’s pull
request heads, fetched from GitHub into a store that borrows the checkout’s objects,
took 0.76 s.

## The Pull Request Header

For [Layout](../../docs/design-system.md#layout), on the pull request page.

Recorded on 2026-11-15, when the header’s last row became the Diff summary: measured in
Chrome 152 at 980 to 320 px on every tab, the row is 24 px from first paint; a summary
of “35 changed files (2 added, 3 removed, 30 modified) +1,234 −3,423” arriving moved no
row and not the tab bar, and kept its row’s 24 px on one line, its breakdown cut short
at 320 px with the whole header as its tooltip; the row starts on the header’s content
edge, and its toggle hangs 4 px into the gutter.
The row adds its 24 px and one 6 px gap to the header.

Recorded on 2026-11-16, when the freshness line became a metadata line and the empty
labels row went: measured in Chrome 152 at 560, 420, and 360 px in both themes, every
row is 6 px under the one before it and the freshness line is 18 px, the row of ages’
height; the header is 229 px with no labels and 255 px with labels or while its record
is on its way, so a labels row that comes or goes moves the tab bar 26 px.
Before, Refresh was a bordered `.btn` that made the line 26 px, an empty 20 px labels
row stood between it and the row of ages, 32 px under that row, and the header was 263
px in every state.

Recorded again on 2026-11-16, when the Diff summary’s statuses became Git’s letters:
measured in Chrome 152 at 980 to 320 px on every tab, a summary of “35 files changed · 2
A, 3 D, 30 M · +1,234 −3,423” arriving moved no row and not the tab bar, and kept its
row’s 24 px on one line, its breakdown cut short at 320 px with the whole header as its
tooltip.

Recorded on 2026-11-17, when the freshness note moved to the end of the author’s row,
Refresh to the end of the row of ages, and the status line came to be there only while
it has something to say (mb-ne91): measured in Chrome 152 at 980 to 320 px on every tab,
the header is 208 px with no labels and 234 px with labels or while its record is on its
way, and 27 px more, a 21 px line and its 6 px gap, while the status line shows, as an
offer makes it; a rate limit’s hold, said in the note’s place, adds nothing.
Before, the freshness line was always there, and the header was 261 px with labels in
every state.
With the recorded record’s login, 38.08 px, its sentence, 153.27 px, and one
stack’s chip, the note, 198.55 px at its widest age, is whole beside the sentence from
980 px to 560 px and out of view from 420 px down; with a 39-character login it is out
of view from 560 px down, and from 760 px with an avatar and two stacks’ chips too.
Wherever it shows, the login and the sentence keep their natural widths.
Shrunk together with the sentence, the note had cut it 0.38 px at 560 px, dropping whole
letters to its ellipsis.

Recorded on 2026-11-18, after review B on #506, measured in Chrome 152 at 980 to 320 px
with the `current` record and one stack’s chip.
A rate limit’s hold in the page’s own short form, “GitHub rate limit · next check at
12/31/98, 4:00 PM”, 288 px, is whole at 980 and 760 px and cut short with its tooltip at
560 px; from 420 px down it keeps its floor, 118 px of text, and the sentence gives way,
to 102 of its 153 px at 420 and 6 at 320. A hold that lifts today, “… next check at 9:23
PM”, 230 px, does the same.
Before, the whole timestamp, 320 px, left the line from 640 px down.
With ages of a record’s length, “Opened 12d ago · updated 5h ago”, 195 px, or 291 px
with “merged 3d ago”, View on GitHub and Browse code show whole down to 420 px, where
the ages have 45 px; at 360 and 320 px the ages are gone and the links are cut, 93% and
73% of them shown. Before, cut at the row’s end, Browse code was cut from 560 px with
every age whole.

## Pull Request Stacks and the Timeline

Recorded on 2026-11-15, when the files-grouping and pull-stacks stack landed.

For [Stacks](../../docs/design-system.md#stacks), the header’s stack chip: measured in
Chrome 152 at 980 to 320 px, one stack’s chip is 54.75 px and two stacks’ 113.5 px; a
late chip moved no part’s start and no row, kept 8 px from the sentence, and cut the
sentence only where it needed the room: at 560 px two stacks cut a long author’s
sentence by 34.88 px, and at 360 px two stacks cut “forker wants to merge 2 commits” by
38.04 px. Measured again on 2026-11-15 once two stacks’ chips named their stacks, “⧉286
4/4” and “⧉300 2/2”: one stack’s chip, “⧉2/3”, is 54.75 px and two stacks’ named chips
156.31 px; a late chip still moved no part’s start and no row and kept 8 px from the
sentence, and at 560 px two stacks cut a long author’s sentence by 77.69 px, and at 360
px “forker wants to merge 2 commits” by 80.85 px.

For
[Stack Groups in the Pulls Tab](../../docs/design-system.md#stack-groups-in-the-pulls-tab):
at the default pane width, 299 px, a worded group-by-stack chip reached 36 px past the
pane and a glyph-only one 7 to 17 px, where the toolbar, the Show group and Reload, has
23 px to spare. A member’s title had 166 px at that width, where a position on the title
line left it 65 to 125.

For [Conversation Timeline](../../docs/design-system.md#conversation-timeline): in
Chrome 152 and in the app’s WebKit alike, a run’s first commit’s glyphs sit 23.5 px
below the card above, and its last commit’s 23.5 px above the card below, against 20 px
between two commits’; before the run kept its room outside it, both were 16 px.
Before this rule, a commit was set at 12 px against the head’s 14 px, its glyphs sat 13
px below the event above, 1 px under its row’s top and 6 px over its bottom, and nothing
joined the events. In the macOS app’s web view (WebKit 21624.2.5.11.8 on macOS 26.5.2),
run through the WebKit gate’s `webkit-driver measure` (`apps/macos/webkit-gate`) on the
same page and layouts, every one of that test’s layout checks passes in both themes,
apart from its pixel reads, which the driver cannot make: an event card computes to
`overflow-x: clip` and `overflow-y: visible`, and in every gap between joined events
WebKit hit-tests the line’s x to the following event’s connector, which it would not do
for a clipped one, and 9 px beside it to the page.
Each node sits 0.5 px below its first line’s middle there, as in Chrome.

Recorded again on 2026-11-15, when every two events took one rhythm,
`--github-pull-rhythm`, at commit 4a46ec4: in Chrome 152 every two events’ boxes are 20
px apart, in both themes and at 980 and 420 px, and their text 20 to 21 px apart, a
commit’s read from its text nodes.
At 420 px a commit row that wraps so that its hash ends it on a line of its own shows
22.5 px below it: the hash’s smaller monospace face leaves 2.5 px of its line under its
glyphs. Review comments stands 28 px below a card; with the rhythm as the body’s gap it
stood 36 px below. Measured once outside that test, the Files and Checks tabs’ notices
are 12 px from what they show, as before the rhythm; with the rhythm as the body’s gap
they were 20 px. Before the rhythm, two cards were 12 px apart, a card and a commit 23.5
px, and two commits 20 px.
In the macOS app’s web view, through the same driver on the same page and layouts at
that commit, the test’s type, spacing, and line checks as they were then pass in both
themes, apart from its pixel reads; each node sits 0.5 px below its first line’s middle,
and every pair of events is 20 px apart, as in Chrome.
What the test holds since has not run in WebKit: the heading checks, the spacing read
from a commit’s text nodes, the break above Review comments, and the rhythm as a margin
above each event rather than the body’s gap.

## Tree Icon Slot

For [One Glyph Size](../../docs/design-system.md#one-glyph-size), recorded 2026-11-15:
at a 16px slot a Files name started 22px from the row’s content edge and a Pulls title
44px, past two slots; at 14px they start at 20 and 40, and a pull request’s title is 4px
wider.

## Pulls Rows

For [The Pulls Tab](../../docs/design-system.md#the-pulls-tab).

Recorded on 2026-11-17, when a Pulls row’s title moved to its first line, after the
state icon, and its number’s line, with the age, to its second; its avatar went from the
shell’s 18 px to 16 px; and a row’s or a stack heading’s statuses became whole or out of
view rather than cut short with an ellipsis.
Measured in headless Chrome 152 in both themes by
`tests/dom/github-pulls-row-lines-chrome.mjs` and
`tests/dom/github-pulls-stack-lines-chrome.mjs`, from 420 px to the 180 px minimum: a
row’s link is still 41 px and its item, with the change line, 61 px, before and after
its line arrives; #106’s line, “2 A, 3 D, 30 M · +1,234 −3,423” in the stand-in, shows
whole down to 299 px and its totals alone from 260 px, where it showed its statuses cut
short before. A stack heading’s line shows whole down to 260 px, its totals alone at 220
and 200 px, and goes at 180 px, where it went before too.
Measured again after review, on hand-built headings in headless Chrome 152 with the
production stylesheet: a heading whose totals are estimated, “21 A, 7 D, 15 M · +1,234
−567 (estimated)”, drops its “(estimated)” whole first and keeps its statuses to 360 px,
then shows its totals alone with nothing after them, and goes at 240 px, as an exact one
does. Before the review’s fix the statuses went at the first pixel of squeeze and left a
blank run of 83 to 115 px, and before this change the note was cut to “(estimat” at 420
px and the line went at 320 px.
`tests/dom/github-pulls-stacks-chrome.mjs` holds the order: the title’s line above the
number’s, the state icon centred on the title’s line, the title from the text column to
the row’s end, and the number’s line in the title’s column.

Recorded on 2026-11-18, when the title-first rows took one leading slot (mb-3vil, at the
owner’s word): measured in headless Chrome 152 by
`tests/dom/github-pulls-stacks-chrome.mjs` at the default 299 px pane, from the pane’s
left edge, a row in no stack has its state icon and its change line’s chevron at 12 px
and its title, its number’s line, and its change line’s values at 32 px, the 14 px slot
and the rows’ 6 px gap past them; a stack’s row has its chevron at 12 px, its Layers
icon at 32 px, and its label at 52 px; and a stack’s member has its state icon and
chevron at 32 px, under the Layers icon, and its three lines’ text at 52 px, under the
label.
A pull request’s changed files start 16 px, one `--tree-indent`, past its chevron.
Before, on the title-first rows, a row in no stack had an empty first slot, its state
icon at 32 px and its title, number’s line, and values at 52 px, with its chevron at 12
px, 26 px from the values.

## Grouping Cost

For [Grouping the Files Tree](../../docs/design-system.md#grouping-the-files-tree),
measured in headless Chrome on a served folder on 2026-11-15: grouping costs the server
a pass over the index per group.
On 22,104 files File type answered in 106 ms where the ungrouped tree took 34 ms, and on
100,000 files in 0.72 to 0.91 s against 0.12 to 0.19 s. Opening a folder inside a
section took 24 to 32 ms, the same as outside one, with no spinner shown.
On a folder of 112 files, a file written every 250 ms for 6 s into a folder open one or
two levels down gave four paced refreshes of at most 8 ms of paint each, and the scroll
position, the focused row inside that folder, and the open folders held through all of
them.

Recorded again on 2026-11-15, once the server read every group from one pass over the
index (`GroupedTreeQuery`), measured in process, warm, against the read per group it
replaced, with identical answers:

| Folder | Ungrouped rows | By file type | By age |
| --- | --- | --- | --- |
| 100,000 files (the bench corpus) | 2 ms | 92–96 ms, was 622–688 ms | 72–98 ms, was 404–505 ms |
| 270,000 files and 110,000 folders | 3–4 ms | 0.42–0.48 s, was 4.0–4.5 s | 0.34–0.47 s, was 3.3–3.6 s |

In headless Chrome on the 100,000-file corpus, a click on By file type painted its
sections 130–132 ms later when the press asked for nothing ahead, and 27–47 ms later
after a 100 ms press had asked for it; By age took 98–116 ms and 29–32 ms; No grouping
painted its tree in 29–49 ms.
On the larger folder By file type took 0.50–0.53 s, or 0.39–0.48 s after a 100 ms press,
and No grouping 41–95 ms.
Two groupings asked for at once each took twice as long there, 0.86 s against about 0.42
s.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
