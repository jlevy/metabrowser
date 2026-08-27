# Continuous Git History Measurements

Status: accepted as the implementation basis for v0.9.0 on 2026-08-26.

Metabrowser v0.8.0 deliberately stops at 500 Git rows.
The v0.9.0 plan removes that logical limit while bounding the browser, server, and Git
process independently of traversal depth.
This report measures the released append-only implementation, prototypes a one-walk
server session, and freezes the structural budgets used by the continuation and virtual
window work.

The Phase 3 implementation now applies the browser budgets directly: decoded pages use
an eight-entry LRU, at most 256 graph rows are expanded and mounted, overscan is bounded
to 64 rows per edge, and the physical scroll segment rebases before 8,000,000 px.
Phase 4 removes the 500-row product ceiling: each session page now carries the versioned
graph-boundary checkpoint that makes an evicted page independently replayable, and the
virtual window follows neighboring page handles in either direction.

Machine timings below describe one development machine.
They explain the chosen structures but are not CI thresholds and do not support a
cross-machine speed claim.
Tests enforce exact ordering and resource bounds instead.

## Method

The product under test is the released v0.8.0 tree at `552f084`, with only the
measurement harness and public names for its shared Git arguments added.
The host was an Apple M1 Pro with 32 GiB memory, macOS 26.5.2, and headed Chrome
151.0.7922.109 at 1600 × 900.

`devtools/git_history_benchmark.py` creates deterministic SHA-1 repositories through a
single `git fast-import` operation.
The matrix contains linear, four-branch unmerged, and repeated-merge histories at 250,
1,000, and 10,000 commits.
Every shape has deterministic timestamps, identities, messages, and file contents.

The backend measurement records the released `--skip` page cost and a prototype that:

- runs one `git log -z --date-order --all` walk;
- frames complete 250-commit pages in a temporary replay spool;
- publishes a page index only after its frame is flushed;
- retains only the current input chunk and page in the parser; and
- replays a page by one indexed seek without touching its prefix.

The original `git-history-depth` baseline forced the all-ref scope and raised the
released row cutoff only inside the measurement document.
The integrated scenario still forces that scope, but now follows the product’s logical
row count to the real end while checking the mounted-row bound, independent page replay,
deepest-row selection, and a fresh deep route.
The product’s normal default ref scope is unchanged.

The accepted mechanism is implemented in `metabrowser.git.history` for Phase 2.
Production freezes the resolved commit tips at session creation, advances the same
ordered walk only when a page is requested, and applies the measured parser, process,
registry, idle, and storage budgets independently.

Run the backend matrix with:

```shell
uv --config-file uv.toml run --frozen python \
  -m devtools.git_history_benchmark matrix \
  .bench/git-history-v090 \
  --output .bench/git-history-v090/backend-matrix.json
```

Run a browser profile against a served generated corpus with:

```shell
node explorations/performance-loop/capture-browser.js \
  --url http://127.0.0.1:8411/view/ \
  --probe explorations/performance-loop/probe.js \
  --output .bench/git-history-v090/browser-linear-10000.json \
  --headed --scenario git-history-depth --history-rows 10000
```

Raw profiles remain under `.bench/` because they contain machine-specific provenance.

## Backend Result

All prototype walks exactly matched `git rev-list --date-order --all`, including the
branch-heavy and merge-heavy histories.
Every sampled first, middle, and final page replayed independently and preserved the
same commit order.

| Shape | Commits | Released page latency range | One-walk time | Peak parser buffer | Replay spool |
| --- | ---: | ---: | ---: | ---: | ---: |
| linear | 250 | 13.2 ms | 9.0 ms | 41.9 KiB | 41.9 KiB |
| linear | 1,000 | 14.4–15.9 ms | 13.9 ms | 86.0 KiB | 167.9 KiB |
| linear | 10,000 | 44.7–47.6 ms | 63.8 ms | 92.4 KiB | 1.66 MiB |
| branch-heavy | 250 | 12.3 ms | 9.6 ms | 41.9 KiB | 42.0 KiB |
| branch-heavy | 1,000 | 14.7–15.2 ms | 13.3 ms | 85.9 KiB | 168.0 KiB |
| branch-heavy | 10,000 | 47.5–49.3 ms | 77.9 ms | 92.4 KiB | 1.66 MiB |
| merge-heavy | 250 | 12.6 ms | 9.5 ms | 46.9 KiB | 46.9 KiB |
| merge-heavy | 1,000 | 14.8–15.6 ms | 14.4 ms | 93.8 KiB | 187.9 KiB |
| merge-heavy | 10,000 | 52.0–70.3 ms | 72.5 ms | 111.4 KiB | 1.85 MiB |

The deepest merge-heavy spool used 194.4 bytes per commit.
The sampled Git child reached 16.9 MiB RSS at 10,000 commits; two simultaneous walks
therefore imply roughly 34 MiB of Git-process memory on this corpus.
The released offset pages still restart Git for every page and accept caller-controlled
depth through the cursor.
Even where this 10,000-commit corpus does not produce dramatic timing growth, that work
shape fails the design requirement: replaying a prior page still walks its prefix again.

## Released v0.8 Browser Result

| Shape | Rows | List DOM nodes | Serialized list | Retained JS heap | API payload | Maximum append | Maximum scroll |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| linear | 250 | 2,501 | 181 KiB | 2.5 MiB | 11.3 KiB | — | 16.7 ms |
| linear | 1,000 | 10,001 | 725 KiB | 3.0 MiB | 45.2 KiB | 131.2 ms | 17.3 ms |
| linear | 10,000 | 100,001 | 7.1 MiB | 10.5 MiB | 452.6 KiB | 706.4 ms | 22.6 ms |
| branch-heavy | 250 | 3,250 | 265 KiB | 2.6 MiB | 11.5 KiB | — | 16.7 ms |
| branch-heavy | 1,000 | 13,000 | 1.0 MiB | 3.2 MiB | 45.7 KiB | 149.6 ms | 16.7 ms |
| branch-heavy | 10,000 | 130,000 | 10.4 MiB | 12.7 MiB | 457.5 KiB | 817.2 ms | 25.0 ms |
| merge-heavy | 250 | 2,875 | 229 KiB | 2.6 MiB | 11.6 KiB | — | 18.0 ms |
| merge-heavy | 1,000 | 11,500 | 917 KiB | 3.1 MiB | 46.4 KiB | 135.0 ms | 17.4 ms |
| merge-heavy | 10,000 | 115,000 | 9.0 MiB | 10.3 MiB | 465.2 KiB | 828.4 ms | 25.0 ms |

Every deepest-row selection converged on the selected, routed, and rendered revision,
retained one comparison, and recorded zero blank frames and page exceptions.
Eight of nine fresh deep routes restored in 0.6–0.9 seconds.
The 10,000-commit branch-heavy route twice failed to render within the separate
30-second diagnostic bound after the full retained-DOM traversal.
That miss is retained as a release requirement for the integrated virtualized path; the
measurement harness does not reinterpret it as success.

Chrome clamped a 100,000,000 px probe to 16,777,214 px.
The 10,000-row list was only 220,008 px, but a truly unbounded fixed-height list would
eventually hit that browser limit.
The virtual scroller must therefore rebase its local segment before 8,000,000 px rather
than depending on one repository-length spacer.

## Phase 4 Integration Result

The integrated headed profile reached the exact final row of the 10,000-commit linear
corpus through 40 sequential pages, then replayed uncached windows at the start,
quartiles, midpoint, and end.
Every replay removed its loading placeholder, the mounted window stayed at or below 165
rows against the 256-row bound, and the final selection and fresh route converged on the
same revision with zero blank frames and page exceptions.

| Logical rows | Mounted rows at end | List DOM nodes | Serialized list | Retained JS heap | Maximum append | Maximum replay | Deep route |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10,000 | 100 | 1,003 | 74.7 KiB | 3.3 MiB | 148.7 ms | 1,300.1 ms | 888 ms |

The profile also exposed a server cleanup defect before acceptance: evicting a live Git
walk could wait on a killed child whose stdout pipe was still full.
Session shutdown now drains that pipe while reaping the child, and a 10,000-commit
resource-eviction regression covers the bound.
Phase 5 repeats the matrix across every measured shape and size and adds a corpus deep
enough to force physical scroll-segment rebasing.

## Frozen Structural Budgets

The constants live in `src/metabrowser/settings.py` and are covered by structural tests.

| Resource | Budget | Evidence and policy |
| --- | ---: | --- |
| page size | 250 commits | The largest measured raw page was 47.5 KiB; this is also the released page size. |
| mounted window | 256 rows | The measured 250-row panel stayed near 2,500–3,250 list nodes and 181–265 KiB. |
| overscan | 64 rows per edge | About 1.8 measured 900 px viewports per edge; shrink it when the visible range approaches the 256-row hard bound. |
| decoded page cache | 8 pages | At measured payload size, 2,000 cached commits occupy about 0.4 MiB of wire data before decoded-object overhead. |
| scroll segment rebase | 8,000,000 px | Less than half Chrome’s measured 16,777,214 px clamp. |
| idle session lifetime | 300 seconds | Gives a reader time to inspect a commit while ensuring abandoned spool files expire. |
| session registry | 8 entries | Bounds idle indexes and spools independently of open browser count. |
| concurrent Git walks | 2 | The measured pair costs roughly 34 MiB of Git-child RSS at 10,000 commits. |
| parser buffer | 128 KiB | Clears the 111.4 KiB merge-heavy peak while retaining one 64 KiB read chunk plus one page. |
| spool storage | 64 MiB per session | About 329,000 visited commits at the measured worst 194.4 bytes per commit; exhaustion expires the session explicitly rather than claiming end of history. |

These are resource budgets, not product-history limits.
A repository may be deeper than the spool estimate.
When an operational budget is exhausted, the server returns the specified expired or
resource-failure state and deletes the session; it never shortens history silently.

## Decision

Accept the one-walk framed replay design for `mb-abu2`. It preserves exact multi-ref and
merge ordering, bounds the parser independently of history depth, and replays an indexed
page without prefix work.

Require the virtual window in `mb-ghju` before removing the v0.8.0 cutoff.
The released append-only renderer is already over 10,000 list nodes and a 100 ms append
at 1,000 rows, then grows past 100,000 nodes and 700 ms append work at 10,000. Raising
the cutoff would convert an honest bound into a progressively worse interface.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
