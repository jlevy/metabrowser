# Rendering Large Content

Metabrowser opens whatever is on disk, so every content view eventually meets a file
larger than its author imagined.
This document is the shared cost model for that case: what is actually expensive in a
2026 browser, which strategies answer it, and the rules that keep limits honest.

It exists because the first version of the binary byte preview shipped a 20 MiB ceiling
it could never have rendered, and the source view shipped a 128 KiB chunk that cost 31
clicks to open a 4 MiB file.
Neither number was measured.
Both looked reasonable.

## Principles

1. **Measure before you bound.** A limit is a claim about cost.
   State the measurement next to the constant, or do not add the constant.
2. **Fix the mechanism before tuning the number.** A small limit is usually a symptom.
   If the only way to stay fast is to stay small, the rendering approach is wrong.
3. **Cost is a shape, not a number.** Learn whether the work is constant, linear, or
   quadratic in content size.
   A quadratic path is unfixable by tuning and always fails later, on someone else’s
   file.
4. **The browser is fast; specific things are slow.** Reading 8 MiB takes milliseconds.
   Wrapping one long text run takes seconds.
   Do not budget against the wrong resource.
5. **Bound what is actually scarce.** Usually browser memory and layout, rarely disk or
   network on a loopback server.
6. **Degrade visibly.** When a bound is reached, the interface says so.
   A silent truncation reads as complete data.
7. **Prefer native behavior.** Real text in the DOM keeps find-in-page, select-all,
   copy, and print. Give that up only for a measured reason, and record the trade.

## What Is Actually Expensive

Measured against Chromium 141 with software raster, so absolute numbers are pessimistic.
The shape is the part that transfers.

### Reading is not the bottleneck

| Operation | Cost |
| --- | --- |
| Plain read, 8 MiB | 4.6 ms |
| Plain read at any offset | O(1) seek |
| Base64 encode, 8 MiB | 9.1 ms |
| Gzip read at 12 MiB offset | 29 ms |

A loopback server reading a file is not worth a tight budget.

Compressed artifacts are the one asymmetry: `ArtifactPath.open_binary` returns a
non-seekable stream, so reaching offset *N* costs decompressing *N* bytes and each
request restarts from zero.
Walking size *S* in chunks of *C* therefore decompresses `S²/2C` in total — which means
a **larger** chunk makes compressed files cheaper, not dearer.
The per-request cost stays linear and small.

A blob on a Git pin is the same asymmetry.
`cat-file` hands out whole objects, not byte ranges, so a window streams the blob from
its start, and Git inflates the object besides; only the window is held.
Measured on a packed store at load average 8:

| Blob | First 2 MiB | Byte view to its 32 MiB ceiling (7 requests) | Worst request |
| --- | --- | --- | --- |
| 8 MiB | 4.6 ms | 72 ms | 28 ms |
| 32 MiB | 7.0 ms | 272 ms | 56 ms |
| 64 MiB | 12 ms | 380 ms | 70 ms |
| 256 MiB | 39 ms | 915 ms | 187 ms |

The same windows from disk took 0.7 ms and about 10 ms.
A blob is not memoized between requests: reading it once and slicing took 40 ms for 32
MiB and 114 ms for 64 MiB over the whole sequence, a saving of well under 100 ms per
click bought by holding the blob in server memory for as long as the view might page.
A blob larger than the pin reads whole is classified from a bounded window the way a
large file is, and a text window ends within `TEXT_PREVIEW_REQUEST_MAX_BYTES`, the
stream budget a compressed file has.

### CSS wrapping one large run is quadratic

Handing the browser a single long text run and asking it to wrap is the expensive
mistake, because the line breaker searches for break opportunities across the whole run:

| Payload | Wrapped lines | Layout and paint | Growth |
| --- | --- | --- | --- |
| 32 KiB | 206 | 43 ms |  |
| 64 KiB | 412 | 146 ms | 3.4x |
| 128 KiB | 824 | 560 ms | 3.8x |
| 256 KiB | 1,648 | 2.17 s | 3.9x |
| 512 KiB | 3,295 | 8.41 s | 3.9x |
| 1 MiB | 6,600 | 33.3 s | ~4x |

Every doubling costs about four times as much.
The wrap mode is not the variable: `overflow-wrap: break-word`,
`overflow-wrap: anywhere` and `word-break: break-all` all landed within 3% of each other
at 256 KiB. What matters is whether the browser has to find the breaks at all.

Content that already contains newlines — ordinary source code — never enters this path.
The source view is fast because `<pre>` defaults to `white-space: pre`, not because
anything clever was done.

### Appending beats re-rendering

Both views originally rebuilt their whole surface on each Load more, so every click cost
the running total rather than the chunk it loaded.
The source view measured 55 ms at 128 KB rising to 152 ms at 1.4 MB. That is linear per
click and quadratic across a sequence — the failure only appears after several clicks,
which is exactly where casual testing stops.

### WebKit lays out a long text node slowly

WebKit lays out one text node of millions of characters several times slower than
Chrome, and nodes of 65,536 UTF-16 code units, the size its HTML parser splits text
into, about as fast.
(Chrome’s parser does not split text.)
Load more appended each chunk as one node, so in WebKit a click cost about 0.5 ms per
KiB of everything loaded.
It now appends nodes of at most that size, `TEXT_NODE_MAX_LENGTH` in `source-append.js`.

The source view’s growth sequence on a 16 MiB source file, from response end to laid
out, as medians of five rounds of back-to-back pairs:

| Load more | Chrome before | Chrome after | WebKit before | WebKit after |
| --- | ---: | ---: | ---: | ---: |
| To 4 MiB, a 2 MiB click | 412 ms | 383 ms | 2,416 ms | 947 ms |
| To 8 MiB, a 4 MiB click | 813 ms | 758 ms | 4,077 ms | 888 ms |
| To 16 MiB, an 8 MiB click | 1,633 ms | 1,584 ms | 8,063 ms | 1,794 ms |

Each round’s after over before was 0.90 to 0.98 in Chrome and 0.22 to 0.39 in WebKit;
opening the file, which the parser builds, did not change in either.
Measured 2026-11-12 on an Apple M1 Pro (MacBookPro18,1), macOS 26.5.2, with Chrome
152.0.7977.83 and WebKit 21624.2.5.11.8 in the macOS app’s web view configuration, at
the app’s 1,200 × 820 window and a load average of 6 to 14 from other work.
Each sample was a fresh browser running the same in-page probe, and each round
alternated which build and which engine went first.

Two costs remain in WebKit.
The first click took 2.45 to 2.51 times Chrome’s time: it takes this file past 100,000
lines, so the gutter gains a digit, the code column narrows, and WebKit lays out all of
the code again where Chrome does not.
With the gutter’s width held by a diagnostic stylesheet, that click took 546 to 555 ms
against Chrome’s 379 to 389 ms.
The 1.4 times left matches the source view’s grid: in one bare-page run, WebKit took
about four times as long to append the same text into a grid like the view’s as into a
plain `pre`. The later clicks took 1.10 to 1.21 times Chrome’s time.

### Syntax highlighting spends elements and main-thread time

Highlight.js lexing is only part of the cost.
Its token markup becomes tens or hundreds of thousands of spans, then the browser must
style and lay out those elements.
Measured in Chromium 141 with software raster, against the vendored grammars and an
attached `<code>` element:

| Grammar | 256 KiB | 512 KiB | 1 MiB | 2 MiB | Token spans, 512 KiB → 2 MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| YAML | 384 ms | 756 ms | 1,686 ms | 3,098 ms | 62,602 → 250,406 |
| Markdown | 244 ms | 340 ms | 674 ms | 1,477 ms | 29,127 → 116,509 |
| JSON | 530 ms | 1,139 ms | 2,133 ms | 4,449 ms | 170,392 → 681,571 |
| TypeScript | 475 ms | 868 ms | 1,850 ms | 3,612 ms | 50,902 → 203,608 |

Each timing combines `hljs.highlightElement` with a forced layout of the attached
result. The growth is broadly linear for these sources, but the absolute work at 1–2 MiB
is already too disruptive for an optional foreground-color enhancement.
The 512 KiB bound keeps the worst measured representative case near one second and
limits the resulting DOM. The shell schedules that work after first paint, so plain,
exact source remains usable while the optional asset or main thread is busy.

### Element count and memory are the real ceilings

Real text in the DOM is what buys native find-in-page and selection, and it is what
costs. The binary view at 32 MiB loaded measured about 87,000 DOM nodes and 306 MB of JS
heap, with scrolling still between 22 ms and 107 ms.
That memory, not any server limit, is what its ceiling protects.

Chrome clamps element height at a measured 33,554,428 px; Firefox is lower.
Any design whose scroll height grows with content meets that wall eventually and needs a
downscaled scrollbar past it.

## The Strategy Ladder

Compared at 1 MiB of byte-preview content:

| Strategy | First paint | Scroll | DOM nodes | Native find, selection, print |
| --- | --- | --- | --- | --- |
| One CSS-wrapped run | 33,333 ms | 32 ms | 12,006 | preserved |
| Pre-broken lines, `white-space: pre` | 633 ms | 33 ms | 16,389 | preserved |
| Pre-broken plus `content-visibility` | 50 ms | 38 ms | 16,420 | preserved |
| Virtualized window | 33 ms | 33 ms | 132 | **lost** |

Climb only as far as the measurement requires.

**Natural lines.** If the content already has newlines, put it in a `white-space: pre`
surface and stop. Layout is proportional to line count.
This is the source view.

**Break the lines yourself.** If the content has no natural lines, compute the breaks
rather than asking CSS to find them.
This is the byte view: it measures the pane, breaks at that column budget, and re-breaks
behind a debounced `ResizeObserver`.

**Add `content-visibility: auto`.** Group lines into blocks so offscreen ones skip
layout and paint. Always pair it with `contain-intrinsic-size`; omitting that is the
documented failure mode, producing scrollbar thrash and broken deep links.

Block size is the tuning knob, because the block is the unit of deferred layout — the
browser pays for one when it scrolls in:

| Block size | Scroll to middle, 8 MiB loaded |
| --- | --- |
| One 4 MiB chunk | 1,788 ms |
| 512 lines | 204 ms |
| 128 lines | 105 ms |
| 64 lines | 127 ms |

**Virtualize.** Render only the viewport window over a spacer.
Flat at any size — 33 ms from 1 MiB through 8 GiB with 132 nodes — and the only option
past a few tens of MB. It gives up browser find-in-page and select-all over the file,
needs scrollbar downscaling past the height clamp, and is substantially more code.
The source and binary content renderers do not virtualize their loaded text.
Navigation collections use a separate policy: the Pulls panel mounts a variable-height
viewport with overscan and protected current or focused rows through
`createPullsWindow`. Git history likewise mounts a bounded logical-row window.
For file content, reach for virtualization when the view must open files larger than
memory allows, and say in the plan what replaces the native behaviors.

Canvas rendering is not on this ladder.
The design system reserves canvas for charts because text must stay selectable.

## Loading Policy

**Open small, grow fast.** Formatting is main-thread work, so the first chunk should be
small enough to appear promptly and later chunks large enough that reaching the end
takes a handful of clicks.
Both views open at 1–2 MiB and double per click to an 8 MiB cap.
The source view went from 31 clicks to open a 4 MiB file to one, and from 127 clicks to
three for 16 MiB.

**Append, never re-render.** A chunk costs what it loaded, not what is already mounted.
When the append cannot be done safely — a syntax-highlighted block, an unexpected view
shape — fall back to a full render rather than dropping content, and keep any status the
render would have refreshed in sync by hand.

**Append text in nodes of at most 64 KiB.** A chunk goes in as text nodes of at most
65,536 UTF-16 code units, the unit a text node’s length counts, which WebKit lays out
several times faster than one long node (see
[WebKit lays out a long text node slowly](#webkit-lays-out-a-long-text-node-slowly)).
Each node ends at its last newline, so ordinary source is split only between lines.
A line longer than the bound is cut between two ASCII characters when the bound falls
there, which is always a grapheme boundary except inside a CRLF. Otherwise, where the
engine has `Intl.Segmenter`, the cut is the start of the grapheme cluster the bound
falls in, segmented from the piece’s start, because a boundary depends on the text
before it: whether a regional indicator starts a flag depends on how many precede it in
its run. An accent, an emoji sequence, or a flag then stays whole.
Without `Intl.Segmenter`, and inside one cluster longer than the bound, the cut is the
last code point boundary that keeps a surrogate pair and a CRLF whole, so an accent can
be cut from its letter.
Segmenting a piece costs time linear in the piece: an 8 MiB line of nothing but flags
took 95 to 97 ms to split in V8 (Node 24) and in WebKit, and 8 MiB lines of ASCII, CJK,
or accented letters and a 1 MiB cluster took 4 to 9 ms.
Copy, find, and selection read across text nodes and see the same text, as checked in
both engines.

**Highlight a bounded prefix, not a small-file category.** For an extension backed by
the shipped grammar registry, the initial source window is capped at the syntax bound
and may be highlighted even when the complete file is much larger.
Truncation and total file size do not disable the bounded prefix.
If Load more takes the visible window past the bound, the source view re-renders the
entire loaded window as plain text once, then returns to incremental appends.
This applies the degradation uniformly instead of leaving an arbitrary colored boundary
on screen.

**Number lines in one text surface.** The source view’s line-number gutter is one
element of text beside the code, in the code’s font and line height, so it costs one
more `white-space: pre` surface rather than an element per line.
Load more appends the numbers of the lines it added, in text nodes within the same 64
KiB bound as the code’s, rather than writing every number again.
Writing them all into the gutter’s first text node, as it did, also left in WebKit the
other nodes its parser had split the gutter into on screen after the new numbers: after
three clicks on the 16 MiB file the page was 10,088,452 px tall, against 9,217,635 px in
Chrome. Building the numbers is 2–4 ms for 4 MiB (56,680 lines); laying the gutter out
adds about 35 ms to a 2 MiB first window (28,340 lines), 135 ms against 100 ms without
it, measured in Chrome on 2026-09-24 on a loaded machine.
The highlight for anchored lines is placed by the height of one rendered line, the
gutter’s height over its line count, measured again when a `ResizeObserver` sees the
gutter change size. A multiple of `1lh` drifts, because line boxes are laid out at
rounded heights: with a 13.1 px code font the `lh` position of line 40,000 is 3 lines
off while the measured one stays on its line.

**One authority per limit.** Sizes live in `settings.py` and reach the client through
`window.METABROWSER_SETTINGS`. A constant restated on both sides of the boundary drifts.

**Batch whole-change-set reprojection.** A diff layout switch updates its control and
root state synchronously.
Above 100 ready files, the renderer reprojects 100 files per task and invalidates stale
batches when a newer layout selection arrives.
The measured 1,000-file fixture kept the cold blocking task below the 200 ms interaction
budget without making ordinary diffs asynchronous.
The current Git manifest cap is `MAX_MANIFEST_FILES`, 2,000 files; that cap does not
extend the older fixture’s timing result to a larger change set.
The repeatable fixture and measurements live in
[Diff layout bound benchmark](../explorations/diff-layout/).

**A visual fold must also be a DOM fold.** A collapsed diff run mounts only its visible
prefix. Expansion adds 100 rows per task, and collapse, reprojection, replacement, and
disposal cancel pending batches and remove their text hosts.
A measured 19,654-line comparison fell from 182,686 to 6,476 total DOM nodes and from a
552 ms longest task to 127 ms.
The browser profile hard-gates `collapsed_diff_rows_materialized` at zero so a CSS-only
fold cannot return unnoticed.

**Bound diff edit-distance work, not input size.** Intraline refinement counts
deterministic dynamic-programming or Myers work per changed run and falls back to the
existing positional rows when that work exceeds 1,000,000 units.
Similar text still refines at the existing 8 MiB patch boundary; unrelated maximum-size
text reaches the bound in at most 32.6 ms across five Chrome 151 runs.
The limit therefore contains the pathological cost without creating a second,
artificially small file-size category.
The fixture and retained-heap evidence live in the
[diff intraline bound benchmark](../explorations/diff-intraline/).

**PR manifests are prepared at fetch.** A PR refresh retains its immutable comparison
manifest in the GitHub plugin’s bounded bank beside its repository store.
A fresh server adopts a validated matching entry after resolving its commits, then uses
the same in-memory comparison cache for the page and deferred files.
Its first answer hydrates eight ready files, enough for the visible viewport measured on
the large public PR cases.
The generic comparison route hydrates up to fifty and includes that policy in the
retained body and entity tag.
Both answers include the available file paths.
These patch budgets keep the first response small.
Missing, stale, or corrupt entries are recomputed and healed; a cache admission bound
never truncates the answer served.
[Pull-request records](project/architecture/arch-repository-sources-and-provider-mirrors.md#pull-request-records)
holds the storage and identity contract.

**A large comparison prepares nearby files.** Each file has a bar as soon as its
comparison opens. `createHydrationScheduler` in `builtin_plugins/diff/diff-view.js` asks
for one file at a time and renders at most one per frame.
It works from the top of the viewport through a short lookahead below it, so it can
start loading a file before it scrolls into view.
After a patch draws, passive loading waits a frame for the pane’s layout to update.
A file jump takes priority.
Scrolling cancels a request that leaves the lookahead or gives its slot to an earlier
file that enters. The diff uses the delayed spinner in the file being fetched.
It shows a notice for an actual failure or truncated result.
While it waits, a file reserves an estimate of its height from the manifest’s line
counts, which keeps a page’s scroll height and a reader’s place close to the truth, and
the first file at the top of the pane stays where it is as files above or inside it fill
in. The route’s 8 MiB bound is per file: see `MAX_FILE_PATCH_BYTES`.

**The mount draws one screen and the next, not every file it was sent.** A comparison’s
first page can be fifty files of rows: on a 1,031-file pull request that was 114,609
nodes, and drawing them in the mount was one task of style, layout and commit of about
1.1 s that every first load, Back and Conversation click waited on.
`mountDiffView` measures the pane and what a bar and a row take, estimates each file’s
top from the rows it will draw, and draws rows only for the ready files whose top is
within the pane and one screen more (`firstScreenBudget`). Every later ready file is a
bar that reserves its own rows, counted from its patch by `patchRows`, and goes through
the scheduler with its patch in hand.
The view draws it on approach or on a jump, one file per frame, nearest the top first.
What it draws is what the mount would have drawn.
A diff that fits is drawn whole, as is one mounted where nothing is laid out to measure.
Measured 2026-11-03 in Chrome 152 on astral-sh/ruff #29817, in adjacent pairs with the
build before at load 9 to 15: 23,451 nodes against 114,609, a longest task of 136 to 330
ms against 653 to 1,182, and the first line 1.4x to 2.0x sooner; every drawn file’s
markup was byte-identical to the build before, and the file at the top did not move.

**Find in page searches what is drawn.** A file’s lines become findable when the diff
draws the file, as it comes near the viewport or when a reader jumps to it.
GitHub’s Files changed has the same limit, since it loads files as they are scrolled to.
Every file’s bar is always in the page, so find in page does find a file by its path:
going to that bar brings the file into the pane, and its lines are drawn as it arrives.
A list of the comparison’s files reaches one with `scrollToFile`, below.

### Going to a file

`scrollToFile(path)` is the diff view’s way to a file, on the handle `mountDiffView`
returns and passed through by the pull-request page’s handle.
It exists for a list of a comparison’s files, so it takes a path and not a file id.

- **A path** is what the file is called now, which is GitHub’s `filename` for a renamed
  file, or else what it was called, its `previous_filename`, or a deleted file’s path.
  `fileForPath(path)` answers whether the comparison holds one, without moving anything,
  typed the same way: `{kind: "file", path, fileId, changeKind, availability}`, where
  `changeKind` is the change’s own kind, or
  `{kind: "not_in_comparison", path, listTruncated}`, and on the page’s handle
  `{kind: "no_diff", path}` while Changes is not mounted, so a list can grey a row the
  comparison lacks and leave alone one it cannot ask about yet.
- **The answer** is immediate and typed, since a list from GitHub and a comparison
  computed here can differ:
  - `{kind: "jumped", fileId, path, availability, lines}`, where `lines` is a promise of
    `"painted"`, `"none"` for a file with nothing to show, `"failed"`, or `"superseded"`
    by a later jump.
  - `{kind: "not_in_comparison", path, listTruncated}`, and nothing moved.
    `listTruncated` says the comparison’s own list stopped at its bound, so the file may
    exist past it.
  - `{kind: "disposed", path}` from a view that is gone, and on the page’s handle
    `{kind: "no_diff", path}` while Changes is not mounted, for which `setTab("files")`
    and `whenFilesReady()` are the way there.
- **The file** is at the top of the pane when it returns, with no smooth scroll,
  expanded if it was collapsed, and stays there as anything else fills in, until the
  reader moves by wheel, touch, pointer or key.
  The key that caused a jump is older than its pin and does not release it, whether a
  list’s handler runs before or after the view’s; a key pressed afterwards does.
  A file too near the end to reach the top gets room past the last file, the same way an
  editor scrolls past its end, because otherwise the files above it filling in push it
  off the screen.
- **Its lines** are asked for first and everything else stops: a request for another
  file is cancelled and the latest jump wins.
  A jump after a quiet moment asks at once.
  A jump within `JUMP_QUIET_MS` of the last, which is a held key, asks only when the
  burst stops, for the file it rests on.
  A ready file the mount held back is the same, except that nothing is asked for: its
  answer is in hand, so its lines are drawn in the frame after the jump, or after the
  burst stops, and its `lines` can be `"superseded"` like any other.

`currentFile()` returns the first file whose bar or body intersects the pane, including
held and deferred files, or `null` when none is visible or the view is disposed.
Its answer has the same fields as `fileForPath`, with the new path for a rename and the
old path for a deletion.
`onCurrentFile(listener)` reports that snapshot immediately, then reports only changes
to the current file; it returns an idempotent unsubscribe function.
Scroll reports share one animation frame and locate the file by bisection over the
ordered sections. Disposal removes the scroll listener, cancels a queued report, and
releases subscribers.

A list calls it on every step of a held key; it is cheap, and it does not need
debouncing. `tests/dom/diff-file-jump-session.js` pins all of this, and
`explorations/performance-loop/experiments/exp-040-files-changed-recomputes-the-whole-patch-per-request.md`
holds the budgets and what was measured against them.

**Fingerprint across chunks.** Every chunked response carries `mtime_hash`; a mismatch
means the file changed, and the view restarts rather than splicing two versions into a
window that never existed on disk.

## Adding or Changing a Limit

1. Reproduce the cost. Serve a fixture at the size in question and drive a real browser,
   following the DevTools recipe in [end-to-end testing](e2e-testing.md).
2. Establish the shape.
   Measure at least three sizes at 2x or 4x steps.
   A constant ratio per doubling means quadratic, and means fixing the mechanism.
3. Separate the variables.
   Element count, block size, and payload size are different knobs; change one at a
   time.
4. Set the limit at a measured size, not a round one.
   If 32 MiB is what you measured, 64 MiB is not a limit, it is a guess.
5. Record the measurement in a comment beside the constant and in the feature plan.
6. Add a contract test for the property, not the timing.
   Assert bounded element counts, preserved content, and structural invariants such as
   “the surface never asks CSS to wrap.”
   Wall-clock assertions are machine-dependent and will be deleted by whoever hits the
   flake.

## Current Limits

| Constant | Value | Bounded resource |
| --- | --- | --- |
| `TEXT_PREVIEW_CHUNK_BYTES` | 2 MiB | Opening latency |
| `TEXT_PREVIEW_MAX_CHUNK_BYTES` | 8 MiB | Per-click main-thread time |
| `TEXT_PREVIEW_REQUEST_MAX_BYTES` | 16 MiB | One request, and the stream window of a compressed file or Git blob |
| `TEXT_NODE_MAX_LENGTH` | 65,536 code units | WebKit’s layout of the text one Load more appends |
| `SYNTAX_HIGHLIGHT_MAX_BYTES` | 512 KiB | Highlight.js main-thread work and token-span DOM |
| `BINARY_PREVIEW_MAX_BYTES` | 32 MiB | Browser memory for loaded bytes |
| `BINARY_PREVIEW_CHUNK_BYTES` | 1 MiB | Opening latency |
| `DEFAULT_ACCENT_RUN_BUDGET` | 60,000 runs | Element count across the mounted view |
| `LINES_PER_BLOCK` | 128 | Deferred layout per scroll-in |
| `LAYOUT_PROJECTION_BATCH_FILES` | 100 files | Diff layout-switch main-thread work per task |
| `FOLD_MATERIALIZATION_BATCH_ROWS` | 100 rows | Diff fold-expansion main-thread work per task |
| `MAX_FILE_PATCH_BYTES` | 8 MiB | One file’s parse and rows in a comparison, and what one run hydrates |
| `JUMP_QUIET_MS` | 50 ms | How long a burst of jumps stops before its last file is asked for |
| `MAX_CACHED_MANIFESTS` | 16 comparisons | Server memory for manifests kept by commit ID: up to 131 MB at the manifest cap, and about 190 MB of RSS, by the measurements beside the constant |
| `MAX_CACHED_BODY_BYTES` | 64 MiB | Server memory for encoded comparison answers |
| `MAX_MANIFEST_FILES` | 2,000 files | Git comparison manifest entries; larger change sets report truncation |
| `WINDOW_ROWS` | 100 rows | One cached-page request by the Pulls panel; automatic catalog backfill is not capped by the display window |
| `DISPLAY_ROWS` | 500 rows | Initial Pulls display budget and each explicit Fetch more increment |
| `PULL_ROWS_OVERSCAN` | 40 rows | Neighbors on either side of the visible Pulls viewport; `createPullsWindow` also retains protected current or focused rows |

A budget that degrades what the reader sees has a second requirement beyond bounding the
resource: the degradation has to apply uniformly to everything on screen.
The accent budget was first spent per chunk and mid-render, which bounded elements
correctly and still produced a visible fault — a 7 MB artifact of readable strings
rendered colored for its first eleven blocks and uncolored for the remaining
sixty-seven, with the boundary falling wherever the budget happened to run out.
Nothing was wrong with the bytes, so the reader could only read the change as one.

The budget is therefore counted across the whole view, decided before any markup is
emitted, and applied to every loaded chunk at once; withdrawing it re-renders what is
already mounted from the retained bytes.
Counting is a pass over bytes with no string building, so deciding costs far less than
rendering does, and the re-render happens at most once per view.
This is the general shape: **decide a degradation against everything the reader can see,
not against the unit you happen to be processing.**

## References

- [Bounded binary byte preview](project/specs/done/plan-2026-08-11-binary-byte-preview.md)
- [Design system](design-system.md)
- [End-to-end testing](e2e-testing.md)
- [MDN: `content-visibility`](https://developer.mozilla.org/en-US/docs/Web/CSS/content-visibility)
- [MDN: `contain-intrinsic-size`](https://developer.mozilla.org/en-US/docs/Web/CSS/contain-intrinsic-size)
- [web.dev: content-visibility](https://web.dev/articles/content-visibility)
- [MDN: `overflow-wrap`](https://developer.mozilla.org/en-US/docs/Web/CSS/overflow-wrap)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
