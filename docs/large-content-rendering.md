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
In WebKit the shapes held but text layout cost more, as
[Measured in WebKit](#measured-in-webkit) records.

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
On a 2x display Chrome laid out half that, 16,777,214 CSS px, so its limit appears to be
in device pixels; WebKit laid out 33,554,428 CSS px there (see
[Measured in WebKit](#measured-in-webkit)). Any design whose scroll height grows with
content meets that wall eventually and needs a downscaled scrollbar past it.

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

**Highlight a bounded prefix, not a small-file category.** For an extension backed by
the shipped grammar registry, the initial source window is capped at the syntax bound
and may be highlighted even when the complete file is much larger.
Truncation and total file size do not disable the bounded prefix.
If Load more takes the visible window past the bound, the source view re-renders the
entire loaded window as plain text once, then returns to incremental appends.
This applies the degradation uniformly instead of leaving an arbitrary colored boundary
on screen.

**Number lines in one text node.** The source view’s line-number gutter is a single text
node beside the code, in the code’s font and line height, so it costs one more
`white-space: pre` surface rather than an element per line.
Building the numbers is 2–4 ms for 4 MiB (56,680 lines); laying the gutter out adds
about 35 ms to a 2 MiB first window (28,340 lines), 135 ms against 100 ms without it,
measured in Chrome on 2026-09-24 on a loaded machine.
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

## Measured in WebKit

**Status:** gate run 2026-11-11 for the macOS app (`mb-gvtw`). It **failed**: from
response to laid out, WebKit took 1.6 to 5.8 times Chrome’s time in the source view and
1.4 to 2.7 times in the binary view, and up to 1.5 times for highlighting and the diff
layout switch. It used much less memory, scrolled the source view faster, and held the
diff mount and intraline budgets.
The decision a failure calls for is open.

Every number above this section is Chrome’s. The
[macOS app research brief](project/research/research-2026-11-08-macos-app-packaging.md)
keeps the app’s Swift shell, a `WKWebView`, only if WebKit holds these bounds: each
bound’s representative case runs in back-to-back pairs against Chrome on one machine,
and WebKit passes when every pair is within 1.3 times Chrome.

### How It Was Measured

- **Harness:** `make macos-webkit-gate` runs
  [`apps/macos/webkit-gate/run.mjs`](../apps/macos/webkit-gate/run.mjs), whose header
  lists its cases and options.
  The original Chrome measurements were scratch harnesses with no committed corpora, so
  the gate measures Chrome again beside WebKit rather than comparing with the numbers
  above.
- **The two engines:** the app’s own web view class (`DropAwareWebView` inside
  `WebContainerView`), built from the app’s `WebConfiguration.make()`, in a window of
  1,200 × 820 points, the app’s default content size; and Google Chrome over the
  DevTools protocol with its viewport set to the same size.
  Both ran at device pixel ratio 2. Each sample is a fresh browser with an empty cache:
  a scratch profile in Chrome, and in WebKit a nonpersistent data store, the one change
  from the app’s configuration.
- **The same inputs:** one `metab` server from the checkout served both engines the same
  generated corpora, whose SHA-256 each run records in its `meta.json`. The diff cases
  are the committed benchmark pages in [explorations](../explorations/README.md), served
  from the same checkout.
- **The same code:** both engines run `probe.js`, injected at document start, which
  opens the view, presses Load more until the file is loaded, scrolls, and times each
  step with `performance.now()` in the page.
- **Pairs:** a warm-up pair, then five pairs per case, alternating which engine goes
  first, so machine load falls on both.
- **The rule:** a pair passes when WebKit’s value is under 1.3 times Chrome’s, and a
  metric passes when every pair does.
  WebKit rounds `performance.now()` to 1 ms (Chrome to 0.1 ms), so a pair of times both
  under 5 ms is reported and not judged.

The metrics:

- **Response end to laid out:** from the end of the view’s request (Resource Timing) to
  a forced layout after the content is in the DOM. It leaves out the server and keeps
  the engine’s work: JSON parsing, building the DOM, style, and layout.
- **Navigation to laid out** and **to next frame:** from navigation start, and the
  second waits for the next rendering update after the forced layout.
- **Click to next frame:** from a Load more click to the rendering update after the
  appended content is laid out.
- **Scroll frame work:** a scroll set at the start of an animation frame, timed to a
  task queued from that frame, so it is the rendering update the scroll caused.
- **Renderer footprint:** the physical footprint of Chrome’s renderer process or
  WebKit’s web content process, from `footprint`, without the graphics memory WebKit
  attributes to the web process and Chrome keeps in its GPU process.

The run behind every number below, on 2026-11-11:

- **Machine:** MacBook Pro (MacBookPro18,1), Apple M1 Pro with 8 performance and 2
  efficiency cores, 32 GB, macOS 26.5.2 (25F84).
- **Engines:** WebKit 21624.2.5.11.8, the build Safari 26.5.2 runs, and Google Chrome
  152.0.7977.83.
- **Server and harness:** `metab` 0.12.1.dev214 from commit `8b0603f7`, and the harness
  as committed in `1c028e84`.
- **Conditions:** a load average of 9 to 15 from other work on the machine; Low Power
  Mode on; the screen locked throughout, so the driver turned off WebKit’s window
  occlusion detection, as Chrome’s `--disable-backgrounding-occluded-windows` does for
  Chrome. Both processes were at scheduling priority 47 when their memory was read.

An earlier complete run that evening, before the driver held off App Nap, failed and
passed the same cases.
Its verdicts differed only on metrics near the line: the diff layout’s slowest switch
passed there (1.12 to 1.21), one binary Load more failed its next frame at 1.30, and
three small scroll and intraline times crossed the 5 ms floor.

### Results

Times are medians of five pairs; a ratio is WebKit’s value over Chrome’s in one pair.

| Bound | Case and metric | Chrome | WebKit | Pair ratios | Verdict |
| --- | --- | ---: | ---: | --- | --- |
| `TEXT_PREVIEW_CHUNK_BYTES` | Source, 16 MiB file: open, response end to laid out | 337 ms | 564 ms | 1.58–1.72 | **fail** |
|  | Open, navigation to next frame | 952 ms | 1,362 ms | 1.31–1.45 | **fail** |
| `TEXT_PREVIEW_MAX_CHUNK_BYTES` | Load more to 4 MiB, response end to laid out | 419 ms | 2,383 ms | 5.63–5.83 | **fail** |
|  | Load more to 8 MiB | 803 ms | 4,004 ms | 4.84–5.06 | **fail** |
|  | Load more to 16 MiB (an 8 MiB click) | 1,664 ms | 7,848 ms | 4.50–4.88 | **fail** |
|  | The same click, to next frame | 2,662 ms | 8,256 ms | 3.05–3.20 | **fail** |
|  | Scrolling 16 MiB, frame work | 85–164 ms | 0–3 ms | 0.00–0.07 | pass |
| One 2 MiB line | Open, response end to laid out | 193 ms | 270 ms | 1.37–1.42 | **fail** |
|  | Open, navigation to next frame | 561 ms | 1,054 ms | 1.84–2.04 | **fail** |
| `SYNTAX_HIGHLIGHT_MAX_BYTES` | YAML, 512 KiB, 27,854 spans | 285 ms | 347 ms | 1.13–1.24 | pass |
|  | Markdown, 4,603 spans | 114 ms | 162 ms | 1.37–1.48 | **fail** |
|  | JSON, 20,307 spans | 212 ms | 251 ms | 1.15–1.22 | pass |
|  | Dense JSON, 307,591 spans | 1,371 ms | 1,699 ms | 1.19–1.25 | pass |
|  | TypeScript, 22,494 spans | 336 ms | 471 ms | 1.27–1.45 | **fail** |
| `BINARY_PREVIEW_CHUNK_BYTES` | Binary, 32 MiB file: open, response end to laid out | 220 ms | 424 ms | 1.86–1.99 | **fail** |
| `BINARY_PREVIEW_MAX_BYTES` | Six Load more clicks to 32 MiB, each response end to laid out | 100–419 ms | 159–960 ms | 1.39–2.46 | **fail** |
|  | Last click (8 MiB), to next frame | 775 ms | 1,335 ms | 1.66–1.77 | **fail** |
|  | Scrolling 32 MiB, frame work | 5.5–6.3 ms | 12–13 ms | 1.76–2.91 | **fail** |
|  | Renderer footprint, without graphics | 1,029 MiB | 238 MiB | 0.23–0.26 | pass |
| `LINES_PER_BLOCK` | Binary, 8 MiB loaded: scroll to the middle, frame work | 2.1 ms | 4.0 ms | 1.25–4.76 | **fail** |
| `DEFAULT_ACCENT_RUN_BUDGET` | Accented binary, 8 MiB, 247,322 elements: open | 88 ms | 197 ms | 2.15–2.36 | **fail** |
|  | Load more clicks, response end to laid out | 77–338 ms | 168–820 ms | 2.13–2.70 | **fail** |
| `LAYOUT_PROJECTION_BATCH_FILES` | Diff layout benchmark, 1,000 files: mount | 59 ms | 26 ms | 0.42–1.08 | pass |
|  | Median blocking layout switch | 22 ms | 31 ms | 1.38–1.47 | **fail** |
|  | Slowest blocking layout switch | 68 ms | 89 ms | 1.21–1.32 | **fail** |
| Intraline work budget | Unrelated long lines, over budget | 36 ms | 21 ms | 0.56–0.58 | pass |
|  | 8 MiB similar line, refined | 24 ms | 26 ms | 1.07–1.11 | pass |
|  | 8 MiB unrelated lines, over budget | 37 ms | 20 ms | 0.51–0.57 | pass |
| Element height | Height laid out for a 100,000,000 px element | 16,777,214 px | 33,554,428 px |  | reported |

The three small intraline cases ran under 5 ms in both engines and are reported, not
judged. The 8 MiB binary’s other scroll positions fell under the floor too; at the
middle, one pair read 10 ms against 2.1 ms.
Every view rendered the same number of elements in both engines, and the tallest scroll
height, 11,772,035 px for the 32 MiB binary, was the same in both.

Renderer footprints without graphics memory were 0.14 to 0.48 of Chrome’s in every view.
With the lightest page, a 2 MiB one-line file, WebKit’s web content process came to 149
to 166 MiB in all, graphics included.
That fits the app’s own measurement of lighter pages, 111 to 143 MB per view
(`apps/macos/scripts/measure-web-views.swift`), and the 155 to 210 MB the
server-topology brief measured with real pages.

### Not Measured

- **Server-side bounds:** the reading and Git blob tables,
  `TEXT_PREVIEW_REQUEST_MAX_BYTES`, `MAX_CACHED_MANIFESTS`, `MAX_CACHED_BODY_BYTES`,
  `MAX_MANIFEST_FILES`, and the server’s half of `MAX_FILE_PATCH_BYTES` bound work in
  `metab`, which is the same whichever engine asks.
- **Rungs no view ships:** CSS wrapping one long run and the strategy ladder’s other
  rows. Contract tests keep every surface off the wrapping path.
- **The diff fold and the first-screen mount:** `FOLD_MATERIALIZATION_BATCH_ROWS` and
  the mount figures came from a 19,654-line comparison and from astral-sh/ruff #29817,
  measured live with no committed fixture.
  The diff layout benchmark’s 1,000-file mount is the nearest committed case, and it is
  in the results.
- **The Pulls panel:** `WINDOW_ROWS`, `DISPLAY_ROWS`, and `PULL_ROWS_OVERSCAN` need a
  pull-request catalog fetched by a signed-in `gh`, which is part of the owner
  acceptance `mb-etqi` keeps.
- **Timers:** `JUMP_QUIET_MS` and the binary view’s resize debounce are delays, not
  costs.

None of these was estimated.

### What the Gate Found

- **Layout is where WebKit falls behind.** In the source and binary views the request,
  JSON parsing, and DOM building took about as long in both engines, and the forced
  style and layout after them took the difference.
  (Highlighting and the diff switch time script and layout together, so they do not
  separate.) JavaScriptCore was faster on pure computation: the intraline edit-distance
  cases ran in 0.51 to 0.58 of Chrome’s time.

- **The source view’s Load more pays most, for its mechanism.** Each click appends the
  chunk as one text node, and WebKit lays out a text node of millions of characters
  three to five times slower than Chrome.
  Its cost grows with all the text loaded, about 0.5 ms per KiB against Chrome’s 0.1, so
  the 8 MiB click into a 16 MiB file took 7.8 s. Three diagnostic cases on a bare page,
  the same corpus in the same 2, 2, 4, and 8 MiB steps, isolate it:

| Appending 16 MiB of source as | Chrome, last step | WebKit, last step | Pair ratios |
| --- | ---: | ---: | --- |
| One text node per chunk, as the source view does | 1,024 ms | 3,297 ms | 3.20–3.35 |
| Text nodes of at most 65,536 characters, as the HTML parser makes | 960 ms | 537 ms | 0.53–0.56 |
| `content-visibility` blocks of 128 lines, as the binary view does | 34 ms | 169 ms | 4.87–5.03 |

Split into parser-sized nodes, the same text lays out faster in WebKit than in Chrome.
Blocks are cheapest in both, but still over 1.3x in WebKit.

- **WebKit does not defer the binary view’s new blocks as Chrome does.** After a chunk
  of `content-visibility` blocks went in, Chrome’s forced layout took under 10 ms and
  WebKit’s 70 to 525 ms on the 32 MiB file, so the binary view, plain or accented, ran
  1.4 to 2.7 times Chrome.
  Highlighting ran 1.1 to 1.5 times and the diff layout switch 1.2 to 1.5: the general
  cost of style and layout in WebKit under these conditions, not one mechanism.

- **Memory and scrolling favor WebKit.** Its web content process used a seventh to a
  half of Chrome’s renderer footprint, and scrolling the 16 MiB source view cost a few
  milliseconds a frame against Chrome’s 85 to 164.

- **The height clamp differs by display scale.** On this 2x display Chrome laid out at
  most 16,777,214 CSS px and WebKit 33,554,428. Neither view came near either limit: the
  tallest scroll height measured was 11,772,035 px.

- **WebKit drew at 30 frames a second throughout**, Chrome at 120, which adds up to 33
  ms to every metric that waits for a frame.
  WebKit throttles animation frames in Low Power Mode, which was on; the machine’s
  settings were not changed to confirm that this was the cause.

- **WebKit’s clock is coarse.** `performance.now()` advanced in 1 ms steps in WebKit and
  0.1 ms in Chrome, which is why pairs under 5 ms are not judged.

The brief’s answer to a failed bound is one of three: make the bound engine-specific,
make a core change that also helps Safari users of the command-line install, or ship
Option F, Electron. The diagnostics suggest the source view’s failure has a small core
fix, splitting appended text at parser size; the binary view, highlighting, and the diff
switch show none. The choice is the owner’s, and this gate leaves it open.

### `window.print()` and Drag and Drop

`run.mjs --checks` scripted both in the app’s web view class and configuration, with the
app’s navigation policy deciding every navigation, on the same machine and versions.
The screen was locked, so no drag could be made by hand: the drags were delivered to the
web view’s own drop methods with a file URL on a private pasteboard, which is what
AppKit delivers for a drag from Finder.

- **`window.print()` does nothing.** The Print button in a file’s header calls it.
  WebKit hands it to two private `WKUIDelegate` methods, `_webView:printFrame:` and
  `_webView:printFrame:pdfFirstPageSize:completionHandler:`, which it asked the delegate
  for; the app implements neither, and no public method exists, so no panel, sheet, or
  modal window opened.
- **File > Print works.** The app prints through `printOperation(with:)` run modally for
  its window. A Markdown document printed as 8 pages of the document alone (Chrome’s
  print of the same page: 9). Run synchronously with `run()` instead, the same operation
  printed blank pages until it was stopped at 865 MB, so it has to stay modal.
  Both engines printed a numbered item’s wrapped lines one word to a line, a defect of
  the print styles rather than of WebKit.
- **A dropped folder opens.** `DropAwareWebView` takes a folder before WebKit sees it
  and hands it to the app, which opens it in a window; the page saw no drag events.
- **A dropped file does nothing.** The page saw `dragenter` and `dragover` carrying
  `Files` and handled neither, so WebKit’s default was to load the file: it asked to
  navigate to its `file://` URL, the policy cancelled that, and the page stayed put.

To check the built app by hand: in a Markdown file’s view, press the header’s Print
button (expect nothing today) and choose File > Print (expect the print panel and the
document); drag a folder from Finder onto a window (expect a new window for it) and a
file (expect nothing).

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
