# Rendering Large Content

**Status:** Current.
Every limit named below is in force; no text view virtualizes its loaded text, and the
table view windows the rows of a large table.
Figures are Chromium 141 measurements with software raster unless a table names another
engine. The diff view’s bounds are in
[Diff Pipeline](project/architecture/arch-diff-pipeline.md), and the macOS app’s WebKit
measurements in [macOS App](project/architecture/arch-macos-app.md).

Metabrowser opens whatever is on disk, so every content view eventually meets a file
larger than its author imagined.
This standard is the shared cost model for that case: what is expensive in a browser,
which strategies answer it, and the rules that keep limits honest, since a limit picked
by feel is wrong one way or the other: a ceiling the view could never render, or a chunk
so small that opening a file takes dozens of clicks.

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

The absolute numbers below are pessimistic; the shape is the part that transfers.
WebKit keeps the shapes but lays text out more slowly.

### Reading is not the bottleneck

| Operation | Cost |
| --- | --- |
| Plain read, 8 MiB | 4.6 ms |
| Plain read at any offset | O(1) seek |
| Base64 encode, 8 MiB | 9.1 ms |
| Gzip read at 12 MiB offset | 29 ms |

A loopback server reading a file is not worth a tight budget.

Compressed artifacts are the one asymmetry: `ArtifactPath.open_binary` (`gz_io.py`)
returns a non-seekable stream, so reaching offset *N* costs decompressing *N* bytes and
each request restarts from zero.
Walking size *S* in chunks of *C* therefore decompresses `S²/2C` in total, so a
**larger** chunk makes compressed files cheaper, not dearer.
The per-request cost stays linear and small.
A blob on a Git pin is the same asymmetry, because `cat-file` hands out whole objects: a
window streams the blob from its start and holds only the window, and the blob is not
memoized between requests.
The measurements behind that choice are beside `read_window` in `git/tree_source.py`.

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
`overflow-wrap: anywhere`, and `word-break: break-all` all landed within 3% of each
other at 256 KiB. What matters is whether the browser has to find the breaks at all.
Content that already contains newlines, as ordinary source code does, never enters this
path: `<pre>` defaults to `white-space: pre`.

### WebKit lays out a long text node slowly

WebKit lays out one text node of millions of characters several times slower than
Chrome, and nodes of 65,536 UTF-16 code units, the size its HTML parser splits text
into, about as fast.
Chrome’s parser does not split text.
So the source view appends nodes of at most `TEXT_NODE_MAX_LENGTH`
(`static/source-append.js`).

The growth sequence on a 16 MiB source file, from response end to laid out, as medians
of five rounds of back-to-back pairs, with each chunk appended as one text node and as
nodes of that bound:

| Load more | Chrome, one node | Chrome, bounded | WebKit, one node | WebKit, bounded |
| --- | ---: | ---: | ---: | ---: |
| To 4 MiB, a 2 MiB click | 412 ms | 383 ms | 2,416 ms | 947 ms |
| To 8 MiB, a 4 MiB click | 813 ms | 758 ms | 4,077 ms | 888 ms |
| To 16 MiB, an 8 MiB click | 1,633 ms | 1,584 ms | 8,063 ms | 1,794 ms |

Each round’s bounded over one-node ratio was 0.90 to 0.98 in Chrome and 0.22 to 0.39 in
WebKit; opening the file, which the parser builds, did not change in either.
Measured 2026-11-12 on an Apple M1 Pro (MacBookPro18,1), macOS 26.5.2, with Chrome
152.0.7977.83 and WebKit 21624.2.5.11.8 in the macOS app’s web view configuration, at
the app’s 1,200 × 820 window and a load average of 6 to 14. Each sample was a fresh
browser running the same in-page probe, and each round alternated which build and which
engine went first.

Two costs remain in WebKit.
The first click takes this file past 100,000 lines, so the gutter gains a digit, the
code column narrows, and WebKit lays out all of the code again where Chrome does not:
that click took 2.45 to 2.51 times Chrome’s time, and 546 to 555 ms against Chrome’s 379
to 389 ms with the gutter’s width held by a diagnostic stylesheet.
The 1.4 times left matches the source view’s grid: in one bare-page run, WebKit took
about four times as long to append the same text into a grid like the view’s as into a
plain `pre`. The later clicks took 1.10 to 1.21 times Chrome’s time.

### Syntax highlighting spends elements and main-thread time

Highlight.js lexing is only part of the cost.
Its token markup becomes tens or hundreds of thousands of spans, then the browser must
style and lay out those elements.
Measured against the vendored grammars and an attached `<code>` element:

| Grammar | 256 KiB | 512 KiB | 1 MiB | 2 MiB | Token spans, 512 KiB → 2 MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| YAML | 384 ms | 756 ms | 1,686 ms | 3,098 ms | 62,602 → 250,406 |
| Markdown | 244 ms | 340 ms | 674 ms | 1,477 ms | 29,127 → 116,509 |
| JSON | 530 ms | 1,139 ms | 2,133 ms | 4,449 ms | 170,392 → 681,571 |
| TypeScript | 475 ms | 868 ms | 1,850 ms | 3,612 ms | 50,902 → 203,608 |

Each timing combines `hljs.highlightElement` with a forced layout of the attached
result.
The growth is broadly linear, but the work at 1 to 2 MiB is too disruptive for an
optional color enhancement.
`SYNTAX_HIGHLIGHT_MAX_BYTES` keeps the worst representative case near one second and
bounds the resulting DOM, and the shell highlights after first paint, so exact plain
source stays usable while the optional asset or the main thread is busy.

### Element count and memory are the real ceilings

Real text in the DOM buys native find-in-page and selection, and it is what costs.
The binary view at 32 MiB loaded measured about 87,000 DOM nodes and 306 MB of JS heap,
with scrolling still between 22 ms and 107 ms.
That memory, not any server limit, is what its ceiling protects.

Chrome clamps element height at a measured 33,554,428 px; Firefox is lower.
On a 2x display Chrome laid out half that, 16,777,214 CSS px, so its limit appears to be
in device pixels, while WebKit laid out 33,554,428 CSS px there.
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
layout and paint. Always pair it with `contain-intrinsic-size`; omitting it is the
documented failure mode, producing scrollbar thrash and broken deep links.
Block size is the tuning knob, because the block is the unit of deferred layout, which
the browser pays for when a block scrolls in:

| Block size | Scroll to middle, 8 MiB loaded |
| --- | --- |
| One 4 MiB chunk | 1,788 ms |
| 512 lines | 204 ms |
| 128 lines | 105 ms |
| 64 lines | 127 ms |

**Virtualize.** Render only the viewport window over a spacer.
It is flat at any size, 33 ms from 1 MiB through 8 GiB with 132 nodes, and the only
option past a few tens of MB. It gives up find-in-page and select-all over the file,
needs scrollbar downscaling past the height clamp, and is substantially more code.
The source and binary views do not virtualize their loaded text; the Pulls panel, the
Git history, the branch and tag chooser, and a table past `WHOLE_TABLE_MAX_ROWS`
virtualize their rows.
The table view states what replaces find, select all, copy, and print
([Data Tables](design-system.md#data-tables)). A rendered Markdown diff past
`WHOLE_UNITS` or `WHOLE_BYTES` draws its blocks a chunk at a time over spacers of
estimated height and never undraws one: a link to a heading draws every chunk through
it, and printing draws them all, while find in page and select all reach only the chunks
drawn ([Markdown Views](project/architecture/arch-diff-pipeline.md#markdown-views)). For
file content, reach for virtualization when the view must open files larger than memory
allows, and say in the plan what replaces the native behaviors.

Canvas rendering is not on this ladder: the design system reserves canvas for charts,
because text must stay selectable.

## Loading Policy

**Open small, grow fast.** Formatting is main-thread work, so the first chunk is small
enough to appear promptly and each Load more doubles it, up to a cap, so reaching the
end of a large file takes a handful of clicks.
The constants are in [Current Limits](#current-limits).

**Append, never re-render.** A chunk costs what it loaded, not what is already mounted.
Rebuilding the surface on each Load more costs the running total instead: linear per
click and quadratic across a sequence, a failure that appears only after several clicks,
where casual testing stops (measured in the header of `static/source-append.js`). When
the append cannot be done safely, as with a syntax-highlighted block or an unexpected
view shape, fall back to a full render rather than dropping content, and keep any status
the render would have refreshed in sync by hand.

**Append text in bounded nodes.** A chunk goes in as text nodes of at most
`TEXT_NODE_MAX_LENGTH` code units, each ending at its last newline, so ordinary source
is split only between lines.
A longer line is cut at a grapheme boundary where the engine can find one; the rules are
beside `cutInsideLine` in `static/source-append.js`. Splitting costs time linear in the
line: in V8 (Node 24) and in WebKit, 8 MiB lines of ASCII, CJK, or accented letters took
4 to 9 ms, a line of nothing but flags 94 to 97 ms, and one cluster of 8 MiB 80 to 91
ms. Copy, find, and selection read across text nodes and see the same text in both
engines.

**Highlight a bounded prefix, not a small-file category.** For an extension backed by
the shipped grammar registry, the initial source window is capped at the syntax bound
and may be highlighted even when the file is much larger.
If Load more takes the window past the bound, the source view renders the whole loaded
window as plain text once, then returns to appending, so the degradation is uniform
rather than an arbitrary colored boundary on screen.

**Number lines in one text surface.** The source view’s gutter is one element of text
beside the code, in its font and line height, so it costs one more `white-space: pre`
surface rather than an element per line; Load more appends the new lines’ numbers in
bounded text nodes. Building the numbers took 2 to 4 ms for 56,680 lines, and laying the
gutter out added about 35 ms to a 28,340-line first window (Chrome, 2026-09-24, a loaded
machine). The highlight for anchored lines is placed by the measured height of one line,
as `static/plugin-sdk-views.js` explains, because positions in `lh` units drift.

**One authority per limit.** A limit has one definition, and the side that does not
define it reads it: the shell reads the server’s sizes from
`window.METABROWSER_SETTINGS`. A constant restated on both sides of the boundary drifts.

**Draw what is near the viewport.** A view that holds more than a screen draws what is
in view and a short lookahead, reserves an estimate of the rest’s height, and keeps the
reader’s place while the rest fills in.
A visual fold is also a DOM fold: collapsed content is not mounted.
The diff view applies both
([Diff Pipeline](project/architecture/arch-diff-pipeline.md)).

**Bound the work, not the input.** Where cost depends on content rather than size, as
edit-distance work does, count the work and fall back past a budget rather than creating
an artificially small file-size category.

**Stop what no estimate bounds.** Where the work depends on what a hostile author can
write and no count over the input bounds it, as KPress’s render of an untrusted document
does, run it where it can be stopped and stop it at a measured deadline, rather than
capping the input’s size.
Every Markdown document rendered under the untrusted profile renders in the server’s
Markdown child (`diff/markdown_projection_worker.py`), which is stopped when a render
runs past its deadline; the refusal is kept by the document for a while, and the page
shows the document’s source with one line saying why.
The child renders one document at a time, so the same module bounds how many distinct
renders wait for it and stops one whose page went away (“One child for both jobs” in its
docstring). A document of any size up to the render route’s own read bound renders if it
finishes in time.

**Fingerprint across chunks.** Every chunked response carries `mtime_hash`; a mismatch
means the file changed, and the view restarts rather than splicing two versions into a
window that never existed on disk.

**Degrade uniformly.** Decide a degradation against everything the reader can see, not
against the unit you happen to be processing.
The binary view’s accent budget is counted across the whole view, decided before any
markup is emitted, and applied to every loaded chunk at once; withdrawing it re-renders
what is mounted from the retained bytes.
A budget spent per chunk colors the first blocks and not the rest, which a reader can
only take for a fault in the bytes.
Counting is a pass over bytes with no string building, so deciding costs far less than
rendering, and the re-render happens at most once per view.

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

Each constant’s value is in its file, with the measurement that set it beside it or in
this standard. Paths are under `src/metabrowser/`.

| Constant | File | Bounds |
| --- | --- | --- |
| `TEXT_PREVIEW_CHUNK_BYTES` | `settings.py` | The source view’s first chunk: opening latency |
| `TEXT_PREVIEW_MAX_CHUNK_BYTES` | `settings.py` | The largest Load more: per-click main-thread time |
| `TEXT_PREVIEW_REQUEST_MAX_BYTES` | `settings.py` | One text request, and the stream window of a compressed file or Git blob |
| `FRONTMATTER_MAX_BYTES`, `FRONTMATTER_MAX_EXPANDED_SIZE`, `YAML_MAX_DEPTH` | `frontmatter_yaml.py` | The front-matter text any path parses, its size with every YAML alias written out, and its nesting; past any of them the front matter is refused, the reason in the answer’s `frontmatter_error_detail`, and the file reads as text |
| `TEXT_NODE_MAX_LENGTH` | `static/source-append.js` | WebKit’s layout of the text one Load more appends |
| `SYNTAX_HIGHLIGHT_MAX_BYTES` | `settings.py` | Highlight.js main-thread work and token-span DOM |
| `BINARY_PREVIEW_MAX_BYTES` | `builtin_plugins/binary/sidekick.py` | Browser memory for the bytes the binary view loads |
| `BINARY_PREVIEW_MAX_CHUNK_BYTES` | `builtin_plugins/binary/sidekick.py` | One byte-chunk request |
| `FIRST_CHUNK_BYTES`, `MAX_CHUNK_BYTES` | `builtin_plugins/binary/bytes-view.js` | The binary view’s first chunk and its largest Load more |
| `DEFAULT_ACCENT_RUN_BUDGET` | `builtin_plugins/binary/byte-format.js` | Accent elements across the mounted binary view |
| `LINES_PER_BLOCK` | `builtin_plugins/binary/bytes-view.js` | Deferred layout per block scrolled in |
| `ROLLUP_MAX_NODES` | `settings.py` | The nodes one Treemap rollup carries: its bytes, the server’s build, and the browser’s parse and decode |
| `PAINT_MAX_CELLS` | `builtin_plugins/folder/treemap-map.js` | The cells a treemap lays out and paints: one relayout’s main-thread time, and the marks a family hover draws |
| `LAYOUT_PROJECTION_BATCH_FILES`, `FOLD_MATERIALIZATION_BATCH_ROWS`, `JUMP_QUIET_MS` | `builtin_plugins/diff/diff-view.js` | Diff main-thread work per task, and when a burst of file jumps asks for its file |
| `MAX_FILE_PATCH_BYTES`, `MAX_MANIFEST_FILES` | `diff/adapters/git.py` | One file’s patch in a comparison, and a comparison’s file list |
| `DIFF_GAP_LINES` | `settings.py` | The unchanged lines one open of a gap between a code diff’s hunks draws and highlights, and the most one `view=lines` answer of the comparison route holds |
| `MAX_LINES_SIDE_BYTES` | `builtin_plugins/diff/sidekick.py` | The side of a changed file a `view=lines` answer reads; past it the file’s separators stay plain |
| `MAX_LINES_ANSWER_BYTES` | `diff/side_lines.py` | The line text one `view=lines` answer carries, and so one press of a gap’s bar draws, which only a side of very long lines meets |
| `MAX_CACHED_MANIFESTS`, `MAX_CACHED_BODY_BYTES` | `builtin_plugins/diff/comparison_cache.py` | Server memory for kept comparisons |
| `KEPT_COMPARISON_CHARS` | `builtin_plugins/github/comparison-prefetch.js` | The document’s memory for the pull-request comparisons its pages read, which outlives every page; the Commits panel keeps its own within `GIT_COMPARISON_CACHE_BYTES` (`settings.py`), so a document holds both |
| `WINDOW_ROWS`, `DISPLAY_ROWS`, `PULL_ROWS_OVERSCAN` | `builtin_plugins/github/pulls-panel.js` | Pulls rows per cached-page request, read at first, and mounted beyond the viewport |
| `INLINE_FOLD_MAX_LINES` | `diff/markdown_views.py` | The source lines a rendered Markdown diff’s fold may span and come with a Concise answer; a longer fold’s blocks are asked for when it opens |
| `FULL_MAX_BLOCKS`, `FULL_MAX_BYTES` | `diff/markdown_views.py` | The blocks and HTML bytes of a Markdown document a pull request’s Docs tab opens in Full rather than Concise |
| `WHOLE_UNITS`, `WHOLE_BYTES` | `builtin_plugins/diff/diff-markdown.js` | The blocks and HTML bytes a rendered Markdown diff may hold and still be drawn whole, keeping the browser’s find and select all; equal to the Full bounds |
| `CHUNK_UNITS`, `CHUNK_BYTES`, `BLOCK_PX`, `BYTE_PX`, `FOLD_PX` | `builtin_plugins/diff/diff-markdown.js` | A longer rendered Markdown diff’s main-thread work per chunk drawn, and the estimated height of a chunk not drawn yet |
| `INERT_RENDER_DEADLINE_MS` | `diff/markdown_projection_worker.py` | One untrusted Markdown document’s render in the server’s Markdown child; past it the child is stopped and the page shows the document’s source |
| `_MAX_RENDERS` | `diff/markdown_projection_worker.py` | Distinct untrusted Markdown renders in flight at once, the one in the Markdown child among them; past it a render is answered `503` with the code `renderer_busy`, which is not kept |
| `ROWS_OVERSCAN` | `static/source-ref-selector.js` | Rows the branch and tag chooser draws beyond its list’s view; the list holds every ref, so the window, not the repository, bounds the rows drawn |
| `TABLE_PAGE_ROWS_DEFAULT`, `TABLE_PAGE_ROWS_MAX` | `table_source.py` | Rows in one page of a table, when a query names no `limit` and at most |
| `TABLE_PAGE_CELLS_MAX` | `table_source.py` | Cells in one page of a table; a page of wide rows carries fewer of them, and its `limit` says how many |
| `TABLE_CELL_PREVIEW_CHARS`, `TABLE_RECORD_VALUE_BYTES` | `table_source.py` | One text value in a page of rows, and in a record; a longer one is cut and says its length |
| `TABLE_CARD_MAX_FIELDS` | `table_source.py` | Fields a table’s hover card shows besides its label |
| `TABLE_TOKEN_MAX_CHARS` | `table_source.py` | A record key or a cursor in a link; a longer one is named by position, valid for one generation |
| `TABLE_REQUEST_DEADLINE_SECONDS` | `table_source.py` | A table request’s work; past it a filter or search answers the rows it found with `complete: false`, and a sort not yet indexed is refused with `sort_budget` |
| `DELIMITED_PARSE_MAX_BYTES`, `DELIMITED_MAX_ROWS`, `DELIMITED_MAX_CELLS` | `builtin_plugins/delimited/source.py` | The bytes, rows, and cells of a `.csv` or `.tsv` file read as a table; past any of them the table holds the leading rows and says so |
| `DELIMITED_MAX_COLUMNS` | `builtin_plugins/delimited/source.py` | The cells of one row of a delimited file read, the header’s among them; past it the table says it was cut |
| `DELIMITED_TYPE_SAMPLE_ROWS` | `builtin_plugins/delimited/source.py` | Rows of a delimited file whose values decide each column’s type |
| `DELIMITED_CACHE_MAX_ENTRIES`, `DELIMITED_CACHE_MAX_BYTES` | `builtin_plugins/delimited/source.py` | Server memory for parsed delimited files and their sort indexes, estimated from each file’s rows, cells, and text |
| `RECORDS_MAX_ROWS`, `RECORDS_MAX_CELLS`, `RECORDS_MAX_FIELDS` | `builtin_plugins/structured/records.py` | The records, top-level values, and fields of a JSON or YAML list read as a table, from the structured plugin’s parse under `STRUCTURED_PARSE_MAX_BYTES`; past any of them the table holds the leading rows or fields and says so |
| `RECORDS_TYPE_SAMPLE_ROWS` | `builtin_plugins/structured/records.py` | Records whose values decide each field’s type |
| `RECORDS_CACHE_MAX_ENTRIES`, `RECORDS_CACHE_MAX_BYTES` | `builtin_plugins/structured/records.py` | Server memory for record lists read as tables and their sort indexes, estimated from each parse’s bytes and nodes |
| `SORT_UNINDEXED_MAX_ROWS` | `builtin_plugins/sqlite/reader.py` | The rows of a SQLite table or view past which only its key and the fields an index leads with sort; the rest say why in `sort_note` |
| `FILTER_SCAN_ROWS` | `builtin_plugins/sqlite/reader.py` | Rows a SQLite filter or search examines before returning a cursor, even when none of them match |
| `OVERVIEW_COUNT_ROWS` | `builtin_plugins/sqlite/reader.py` | Rows counted for a SQLite overview table without ANALYZE statistics. A larger table’s size is omitted |
| `COUNT_CAP` | `builtin_plugins/sqlite/reader.py` | The rows a SQLite page’s count reads; past it the count is a lower bound, drawn as “at least” |
| `REFS_PER_PAGE` | `builtin_plugins/sqlite/reader.py` | Referenced rows one SQLite page resolves; a value past it is shown without its reference |
| `PAGE_INLINE_BYTES` | `builtin_plugins/sqlite/reader.py` | A SQLite text or blob a page reads whole; a longer one is previewed from its stored bytes, or shown as its size where it has no rowid |
| `DESCRIPTION_CACHE_ENTRIES` | `builtin_plugins/sqlite/database.py` | Server memory for SQLite catalogs and table descriptions, by database and generation |
| `WHOLE_TABLE_MAX_ROWS` | `builtin_plugins/table/table-view.js` | The rows a table may hold and still be drawn whole, keeping the browser’s find, select all, copy, and print; a larger one is a window with Search, row selection that copies as tab-separated values, and print of the rows held in their place |
| `FILE_WATCH_MAX_PATHS` | `file_watches.py` | Files one page may watch on its event stream, which every poll reads the generation of; a watch past it is refused and its view is not live |
| `FIRST_PAGE_ROWS`, `NEXT_PAGE_ROWS`, `ROWS_OVERSCAN`, `ROW_HEIGHT_ESTIMATE_PX` | `builtin_plugins/table/table-view.js` | The rows the table view’s first and later requests ask for, which a page of wide rows may answer with fewer, the rows its window draws past the view, and a row’s height before one is measured |
| `PRINT_MAX_ROWS` | `builtin_plugins/table/table-view.js` | The rows a printout of a windowed table draws; past it, or when rows after those held were not read, the printout says which rows it holds. The comment above it records why the rows a window holds have no bound of their own |
| `VALUE_MAX_BYTES`, `READ_OPCODE_BUDGET` | `sqlite_access.py` | The longest value one SQLite statement may produce, and the virtual-machine steps one read may run, beside a wall-clock deadline its watchdog interrupts at |
| `COPY_MAX_BYTES` | `sqlite_access.py` | A database and its log copied privately for one read, when its log has no index or the file has a second name; past it the main file is read alone and says so |
| `READER_POOL_SIZE`, `READER_QUEUE_MAX`, `SQLITE_REQUEST_DEADLINE_SECONDS`, `READER_KILL_GRACE_SECONDS`, `READER_ADDRESS_SPACE_BYTES` | `sqlite_readers.py` | SQLite reader processes alive and requests waiting for one, a request’s deadline and the grace before its reader is killed, and a reader’s address space |
| `BLOB_MAX_BYTES`, `BLOBS_MAX_BYTES` | `sqlite_readers.py` | A database on a Git pin, written once to a private file to be read, and the written blobs one process keeps, the least recently used removed past it |
| `ANSWER_MAX_BYTES`, `HEAP_LIMIT_BYTES` | `sqlite_access.py` | The longest answer a SQLite reader process returns, past which it answers `too_large`, and the heap SQLite may allocate in one, which bounds it where the address-space limit is not enforced |
| `SUMMARY_ROWS_OVERSCAN` | `builtin_plugins/diff/diff-summary.js` | Diff summary rows mounted on either side of the window’s view of its tree, which has no scroll of its own and no length bound beyond `MAX_MANIFEST_FILES` |

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
