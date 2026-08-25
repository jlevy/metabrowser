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
No Metabrowser view uses it yet.
Reach for it when a view must open files larger than memory allows, and say in the plan
what replaces the native behaviors.

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

**One authority per limit.** Sizes live in `settings.py` and reach the client through
`window.METABROWSER_SETTINGS`. A constant restated on both sides of the boundary drifts.

**Batch whole-change-set reprojection.** A diff layout switch updates its control and
root state synchronously.
Above 100 ready files, the renderer reprojects 100 files per task and invalidates stale
batches when a newer layout selection arrives.
This keeps the cold blocking task below the 200 ms interaction budget at the server’s
1,000-file manifest bound without making ordinary diffs asynchronous.
The repeatable fixture and measurements live in
[Diff layout bound benchmark](../explorations/diff-layout/).

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
| `TEXT_PREVIEW_REQUEST_MAX_BYTES` | 16 MiB | One request, and the decompression window |
| `SYNTAX_HIGHLIGHT_MAX_BYTES` | 512 KiB | Highlight.js main-thread work and token-span DOM |
| `BINARY_PREVIEW_MAX_BYTES` | 32 MiB | Browser memory for loaded bytes |
| `BINARY_PREVIEW_CHUNK_BYTES` | 1 MiB | Opening latency |
| `DEFAULT_ACCENT_RUN_BUDGET` | 60,000 runs | Element count across the mounted view |
| `LINES_PER_BLOCK` | 128 | Deferred layout per scroll-in |
| `LAYOUT_PROJECTION_BATCH_FILES` | 100 files | Diff layout-switch main-thread work per task |

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
