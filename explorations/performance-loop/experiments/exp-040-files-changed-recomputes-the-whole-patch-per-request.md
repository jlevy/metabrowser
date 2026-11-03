---
title: Files changed on a large pull request recomputes the whole patch on every request, and one deleted empty file makes it fail outright
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-040
  title: Files changed on a large pull request recomputes the whole patch on every request, and one deleted empty file makes it fail outright
  date: "2026-11-02"
  hypotheses: []
  subject:
    corpus: >-
      the default cache's mirror of a private 1.2 GB repository (329,135 packed objects,
      269 refs) and its cached pull-request records, served at each pull request's head
      by the stable build; the pull requests are named here by shape only. For the
      GitHub comparison, mirrors of three public repositories in an isolated cache:
      astral-sh/ruff (244 MB), scikit-learn/scikit-learn (202 MB) and python/typeshed
      (38 MB). corpus_files is the changed-file count of the stress case
    corpus_files: 1183
    host_cpu: Apple M1 Pro, 10 cores
    host_system: Darwin 25.5.0, CPython 3.14.7, git 2.50.1, gh 2.x
    browser: >-
      visible, foregrounded Google Chrome 152.0.7977.83 driven over the DevTools
      Protocol, one fresh browser context per run; github.com was loaded logged out
    viewport: "1400x900"
    cold: true
  method:
    runs_per_condition: 3
    interleaved: true
    control: >-
      the stable build, metab 0.11.1.dev738+87dc21f4, the top of the release stack,
      from its own installed environment; and github.com logged out, for the bar
    candidate: >-
      the same build with a scratch hack of three parts, applied to a copy of the
      package outside the repository and run through the worktree's locked environment:
      a pathspec-limited patch that reuses the manifest, an in-memory comparison cache
      with an immutable Cache-Control, and a prefetch of Files changed from the
      Conversation tab. No product code changed on any branch
    record: >-
      scripts, raw JSONL and server logs under the session scratchpad, prperf/, and the
      hacked package copy beside it under hack/; nothing here was recorded with run.py,
      whose ledger measures a served folder's first tree rows, not a pull request. Load
      average on the ten cores ran from 2.5 to 45 across the day; every table says which.
      Instructions retired were not read: the differences here are tens of times, not
      five percent
  results:
    - metric: comparison_route_repeat_ms_1183_files
      control_median: 8766.8
      candidate_median: 43.4
      control_range: [6935.0, 10646.5]
      candidate_range: [42.7, 118.8]
      change_pct: -99.5
      overlapping: false
    - metric: comparison_route_first_ms_1183_files
      control_median: 7566.1
      candidate_median: 1773.7
      control_range: [7566.1, 7566.1]
      candidate_range: [1773.7, 1773.7]
      change_pct: -76.6
      overlapping: false
    - metric: one_deferred_file_hydration_ms_1183_files
      control_median: 12666.3
      candidate_median: 3.4
      control_range: [8774.0, 13895.8]
      candidate_range: [3.0, 22.6]
      change_pct: -100.0
      overlapping: false
    - metric: comparison_route_status_663_files_incidental
      control_median: 404
      candidate_median: 200
      control_range: [404, 404]
      candidate_range: [200, 200]
      change_pct: -50.5
      overlapping: false
    - metric: comparison_route_repeat_ms_42_files
      control_median: 297.6
      candidate_median: 35.4
      control_range: [255.5, 359.4]
      candidate_range: [34.6, 90.0]
      change_pct: -88.1
      overlapping: false
    - metric: files_changed_first_diff_line_ms_1183_files
      control_median: 6677
      candidate_median: 1145
      control_range: [6260, 7093]
      candidate_range: [1022, 1267]
      change_pct: -82.9
      overlapping: false
    - metric: back_to_files_first_diff_line_ms_1183_files
      control_median: 7422
      candidate_median: 529
      control_range: [7029, 7815]
      candidate_range: [502, 555]
      change_pct: -92.9
      overlapping: false
    - metric: conversation_to_files_click_first_diff_line_ms_1183_files
      control_median: 7655
      candidate_median: 590
      control_range: [7226, 8083]
      candidate_range: [557, 622]
      change_pct: -92.3
      overlapping: false
    - metric: conversation_to_files_click_first_diff_line_ms_42_files
      control_median: 510
      candidate_median: 153
      control_range: [379, 641]
      candidate_range: [141, 165]
      change_pct: -70.0
      overlapping: false
  complexity:
    lines_changed: 0
    new_dependencies: []
    new_failure_modes: []
    notes: >-
      A measurement round. The hack that proves the gains lives outside the repository
      and is described, not merged; its parts are ranked under Fixes.
  verdict:
    decision: baseline
    primary_metric: files_changed_first_diff_line_ms
    reason: >-
      On the stable build the time to a pull request's first diff line grows with the
      size of the pull request, from 0.36 s at 3 files to 8.0 s at 1,183 files, and
      a 663-file pull request shows no Files changed at all: the comparison route
      answers 404, because the patch parser cannot model a deleted empty file and the
      route throws the whole comparison away when one section fails. A public
      301-file pull request fails the same way. The slowness is one route that runs
      the manifest twice, diffs the whole comparison, parses up to 8 MiB of it in
      Python and keeps none of it, on every request, including each on-demand
      hydration of a deferred file. A scratch hack that limits the patch to the
      hydrated files and keeps the comparison in memory takes the 1,183-file route
      from 4.4 s to 43 ms on a repeat and the per-file hydration from 4.4 s to 3 ms.
      Nothing is accepted: the hack is a proof, not a change.
    commit: 87dc21f4
---
# exp-040: Files changed on a large pull request recomputes the whole patch on every request, and one deleted empty file makes it fail outright

## The question

How fast does the stable build show a large pull request, is that as fast as it can
reasonably be, and is it faster than github.com?
Metabrowser holds a local mirror and a cached record; GitHub has a network and a server.
The owner’s standard is “effortlessly fast”: prefetch by default, and never a spinner
under about 50 ms. If the page is not clearly faster than GitHub, this record says
exactly why.

## What was run

The subjects, all from one private 1.2 GB repository, described by shape:

| Shape | Files | Lines | Commits | State | Why |
| --- | ---: | ---: | ---: | --- | --- |
| the stress case | 1,183 | +281,131 −5,988 | 1,218 | open draft | the largest open pull request |
| the long-files case | 17 | +13,417 −15 | 29 | merged | few, very long files |
| the large merged case | 42 | +10,231 −0 | 15 | merged | ordinary large |
| the reviewed case | 42 | +7,786 −30 | 12 | merged | 8 comments, 5 reviews |
| the open case | 27 | +5,968 −81 | 8 | open | not a draft |
| the edited case | 7 | +3,895 −1,808 | 11 | merged | edits rather than additions |
| the control | 3 | +51 −16 |  | merged | small |
| the mass-deletion case | 663 | +16,359 −175,715 |  | merged | found among the older 900 |
| the giant-additions case | 101 | +442,186 −2 |  | merged | the largest by lines |

The last two came from paging the repository’s pull requests through GraphQL fifty at a
time with only the size fields asked for; `gh pr list --limit 1000` fails on its own
node budget, and the pages stopped at 900 on an HTTP 502 from GitHub.

Three layers were measured, each by hand and not through the harness:

- **Server:** `/api/plugin/github/pull` and `/api/plugin/diff/comparison`, with
  `Accept-Encoding: gzip`, first request and repeats, from a Python client reading
  `Server-Timing`, transferred and decoded bytes, `ETag` and `Cache-Control`.
- **Git:** the commands the comparison route runs, run by hand on the mirror with the
  route’s own options, and the product’s own parser on their output.
- **Browser:** a recorder injected before any page script stamps the first appearance of
  each reader-visible element and the second animation frame after it, which is when it
  has been painted; it also collects Long Tasks, LCP, CLS and Event Timing.
  Trusted input through the DevTools Protocol scrolls, clicks the layout control,
  collapses a file, goes Back through history, opens a file, jumps to a file by number,
  and holds a key through consecutive files.
  Every run checked `document.visibilityState` and every run was `visible`.

The machine was never quiet.
Other agents ran all day; the one-minute load average on ten cores was 2.5–4 for the
first server and Git series, 8–45 for the browser series.
Every table below carries the load it was taken under.
Wall-clock figures under load 20 or more are rough, and the list at the end says which
ones a quiet machine should take again.
The differences that matter here are tens of times, which load does not manufacture.

## The headline

**On the largest pull request the page is not slow; it is broken in two of its shapes,
and slow in the third.**

1. The 663-file mass-deletion pull request has no Files changed.
   The comparison route answers
   `404 {"message": "file 'f1' not found in the produced diff"}` after 1.8 s, every
   time. Thirteen of its sections delete an empty file: `diff --git`,
   `deleted file mode 100644`, an `index` line, no hunks.
   `parse_unified_patch` cannot model that section (one validation error for
   `ChangeSetDocument`), and when any section fails it returns an empty document with a
   warning rather than the sections it could model; `file_patches` then cannot find file
   `f1` in it and the route refuses the whole comparison, although `f1`’s own patch is
   512 bytes. A synthetic patch of one ordinary modification plus one deleted empty file
   parses to zero files; an added empty file and a mode-only change parse fine.
   The public 301-file baseline pull request has one such section and fails the same
   way, with a 1.3 MB patch nowhere near any bound.
   The page says “file ‘f1’ not found in the produced diff” where the diff would be.
   This is a correctness bug, not a performance one, and it is the first thing to fix:
   any pull request that deletes an empty file, an empty `__init__.py` for one, has no
   Files changed.
2. The 101-file, +442,186-line pull request answers in 3.9 s with 13.5 MB of JSON
   decoded (339 KB on the wire): fifty files hydrated whole, and the browser then has to
   parse and render them.
   The same 3.9 s again for every deferred file the reader scrolls to.
3. The 1,183-file pull request answers in 4.4 s, and again 4.4 s for every one of the
   1,130 deferred files as the reader reaches it, two at a time.
   Reading past file 50 costs a 4.4 s wait per file.
   The first diff line paints at 8.0 s; the title and tabs at 0.3 s.

The cause is one function.
`comparison_handler` in `builtin_plugins/diff/sidekick.py` computes the manifest (two
`git diff` runs with `-M50 -C`), then calls `GitDiffSource.file_patches`, which computes
the manifest again (two more), runs the unrestricted patch of the whole comparison,
parses up to 8 MiB of it in Python, and keeps fifty files of the result.
Nothing is cached between requests, the response carries no `ETag` and no
`Cache-Control`, and the on-demand loader for one deferred file (`&file=`) runs the same
whole-comparison diff and parse to return one file.
Every cost on the route scales with the size of the pull request, and the reader only
ever sees fifty files of it at once.

A scratch hack that passes the manifest through, limits the patch to the hydrated files’
paths, keeps the comparison in memory and marks the response immutable takes the
1,183-file route to 43 ms on a repeat and each hydration to 3 ms, and makes the 663-file
pull request load. The sections below are the measurements.

## Start-up

`metab <pull URL> --no-serve` for an already cached pull request took 6.2 s under a load
average of 3; the stable build in serve mode answered its first request 0.74–0.99 s
after spawn for a cached pull request and 7.6 s for one never fetched (load 8–19). The
mirror has 269 refs, 260 of them remote branches: ref count is not the cause.

The seconds are process spawns of `gh`, counted by a shim on `PATH` that logs each call
and its wall time. One `--no-serve` of a pull request not yet in the cache:

| Step | Calls | Each | Together |
| --- | ---: | ---: | ---: |
| Python start, cache open, record read |  |  | 0.4–0.7 s |
| `gh auth status` | 2 | 0.37–0.51 s | 0.8–1.0 s |
| `gh api` for the pull, its issue comments, reviews, review comments, check runs and status, in sequence | 6 | 0.44–0.93 s | 3.0–4.0 s |
| `gh auth git-credential get`, `store` | 2 | 0.04–0.07 s | 0.1 s |
| `git fetch` of `refs/pull/<n>/head`, then `merge-base` |  |  | 0.9–1.4 s |
| Total | 10 |  | 5.5–6.6 s |

The six API calls take the same time when they answer 304 as when they answer 200: the
cost is spawning `gh` and its TLS handshake, not the payload.
The 1,218-commit pull request cost nothing extra: commits are counted, never listed.
GitHub’s own rate-limit budget was touched six times per refresh.
Serve mode defers the refresh rather than skipping it: a server for a cached pull
request answered its first request in 1.1 s and then, because the record was older than
the 60 s freshness window, spent fourteen `gh` spawns in the background, the same eight
plus three credential pairs for three fetches, while the page polled the pull route once
a second until the refresh ended, five polls on the stress case, each a 304.

The physical lower bound is one authenticated connection and six requests in flight
together, about 0.3–0.5 s, or one GraphQL request.
Six sequential spawns of a CLI are ten times that.
The 11 s the coordinator saw is this same path under a higher load.

## The server routes

Taken from a Python client on the same machine, three to five repeats after a first
request, load average 3.4–5.9.

| Pull request | Pull route first / repeat | 304 | Comparison first / repeat | Wire / decoded | Hydrated | One deferred file |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 3 files | 15.5 / 1.1 ms | 0.8 ms | 81 / 71 ms | 3.5 KB / 16 KB | 3 of 3 |  |
| 17 files, +13,417 | 15.4 / 1.4 ms | 0.8 ms | 200 / 197 ms | 137 KB / 1.03 MB | 17 of 17 |  |
| 42 files, +10,231 | 17.8 / 1.8 ms | 0.8 ms | 174 / 167 ms | 144 KB / 906 KB | 42 of 42 |  |
| 101 files, +442,186 | 15.4 / 1.1 ms | 0.8 ms | 3,910 / 4,056 ms | 339 KB / 13.56 MB | 50 of 101 | 3,816 ms |
| 663 files, −175,715 | 14.9 / 7.8 ms | 0.8 ms | **404** in 1.8 s |  | none |  |
| 1,183 files, +281,131 | 21.1 / 1.3 ms | 0.9 ms | 4,397 / 4,412 ms | 197 KB / 1.04 MB | 50 of 1,183 | 4,376 ms |

What the table says:

- The pull route is right.
  It serves a parsed record from memory, answers a poll with a 304 in under a
  millisecond, and its time is independent of the pull request.
  Its `Cache-Control` is `no-store`, which is correct for a record that a refresh
  replaces.
- Compression is on: gzip at level 6 for bodies over 1 KiB, 6x on an ordinary comparison
  and 40x on the giant-additions case, whose 13.5 MB is mostly line numbers and
  whitespace.
- The comparison route caches nothing across requests.
  A repeat costs what the first did, and the second request is not faster.
  It carries no `ETag` and no `Cache-Control`, so the browser cannot cache it either:
  Back to Files changed fetches it again in full.
- The time grows with the whole pull request, not with the fifty files served.
- The route’s time includes `Server-Timing` of the same value, so none of it is
  transfer.

## Git underneath

The route’s commands run by hand on the mirror, five repeats, load average 2.5–3.6, with
the product’s parser and serializer run on the patch in the same process:

| Command | 42 files | 17 files, long | 1,183 files | 663 files | 101 files, +442k |
| --- | ---: | ---: | ---: | ---: | ---: |
| `merge-base` | 12.5 ms | 13.0 ms | 88.9 ms | 16.9 ms | 12.9 ms |
| `diff --raw -z -M50 -C` | 13.8 ms | 17.8 ms | 515.7 ms | 75.2 ms | 15.1 ms |
| `diff --numstat -z -M50 -C` | 16.5 ms | 21.0 ms | 642.3 ms | 130.0 ms | 90.1 ms |
| `diff` whole patch, `-M50 -C` | 18.7 ms, 480 KB | 23.6 ms, 479 KB | 735.9 ms, 14.8 MB | 155.7 ms, 9.5 MB | 167.8 ms, 8.26 MB |
| `diff` limited to the first 50 paths | 19.3 ms | 23.9 ms | **25.8 ms, 354 KB** | 33.5 ms, 792 KB | 69.8 ms, 4.4 MB |
| `diff` limited to one path | 13.1 ms | 13.3 ms | 13.7 ms | 19.1 ms | 13.0 ms |
| `cat-file --batch`, 20 blobs | 13.7 ms | 14.6 ms | 14.5 ms | 18.8 ms | 16.0 ms |
| `parse_unified_patch` of the whole patch | 45.9 ms | 60.9 ms | 1,262.8 ms, truncated: 677 of 1,183 | 1,070.9 ms, truncated: **0 files** | 3,447.6 ms, 92 of 101 |
| `dump_document` + `json.dumps` | 9.5 ms | 12.4 ms | 243.5 ms, 16.3 MB |  | 712.5 ms, 29 MB |

A Git process on this mirror costs about 12–13 ms to start and answer anything, which is
the floor for every row; `merge-base` on the stress case is 89 ms because its base is
far down a long history.

Where the stress case’s 4.4 s goes, adding the rows the route runs:

| Stage | Cost | Needed |
| --- | ---: | --- |
| `rev-parse` left and right, `merge-base` | ~0.12 s | once per comparison, then never |
| manifest: `--raw` and `--numstat` | 1.16 s | once per comparison, then never |
| manifest again, inside `file_patches` | 1.16 s | not at all |
| whole patch, 14.8 MB | 0.74 s | 26 ms for the fifty files served |
| Python parse of the first 8 MiB | 1.26 s | ~35 ms for the fifty files served |
| model copies, dump, JSON | ~0.1 s | the same |
|  | **≈4.5 s** | **≈1.4 s once, then microseconds** |

And then the same again for each `&file=` request, which parses 8 MiB to answer with one
file.

The manifest’s own 1.16 s is mostly copy detection.
On the stress case, under a load of 33 so the ratios are what count: `--raw` without
renames 37 ms, `-M50` 71 ms, `-M50 -C` 681 ms; `--numstat` 241, 434 and 783 ms.
`-C` looks for copy sources among every changed file and costs ten times the listing.
GitHub does not show copies.
With `-M50` alone the manifest of 1,183 files is about 0.5 s, and `--numstat` is the
part that has to inflate every changed blob to count its lines, which is the manifest’s
physical floor: about a quarter second for 281,000 added lines here, and a number that
can be computed once at fetch time rather than on a request.

The 663-file case is the parser’s, not Git’s: 663 sections in 9.5 MB, and the thirteen
validation errors are its thirteen deleted empty files, each refused on its own, as
[The headline](#the-headline) describes.
The 8 MiB cut is a second, separate edge: 564 of the sections are inside the first 8 MiB
and the cut lands in the 565th; on the stress case the cut keeps 677 of 1,183 files, and
the route then asks for fifty of them.
The limit was sized for a patch file a reader opens; it is applied to a comparison
nobody chose the size of.

## What a reader sees

Visible Chrome, fresh browser context per run, three runs per condition, Files changed
in split layout, from navigation start to the second animation frame after the element
appeared. Load average in the left column.

| Pull request | Load | Title, tabs | Files summary | First diff line | All file bars | LCP | Long task max | Long tasks | DOM nodes | JS heap after GC | Comparison on the wire |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 3 files | 9 | 180 (157–473) | 356 (331–731) | 356 | 356 | 388 | 0 | 0 | 3,588 | 12 MB | 71 ms |
| 42 files | 12 | 285 (195–301) | 685 (595–910) | 685 | 685 | 308 | 111 ms | 1 | 9,882 | 16 MB | 461 ms |
| 17 files, long | 23 | 349 (255–1,094) | 923 (763–1,747) | 923 | 923 | 372 | 73 ms | 2 | 6,046 | 33 MB |  |
| 1,183 files | 30 | 317 (289–1,084) | 8,026 (7,941–9,590) | 8,026 | 8,026 | 8,056 | **593 ms** | 5 | **43,788** | 13 MB | 6,419 ms |
| 101 files, +442k | 19 | 198 (163–452) | 5,107 (4,337–6,102) | 5,107 | 5,107 | 5,196 | 131 ms | 3 | 13,290 | **151 MB** | 16.4 MB decoded |
| 663 files, −176k | 35 | 293 (261–786) | never | never | never | 316 | 0 | 0 | 1,222 | 9 MB | 404 |

Milliseconds; medians with ranges.
The 663-file page shows the server’s message, “file ‘f1’ not found in the produced
diff”, where the diff would be.
The giant-additions case holds 151 MB of JavaScript heap after garbage collection for
fifty files, settles 8.7 s after navigation because syntax highlighting of 442,000 lines
takes 1.26 s serialized after the mount, and its Back costs 6.8 s (4.4–7.8). Scrolling
it from the first file reached 24 deferred files, and the hydrations those queued, at
3.8 s each and two at a time, had not finished 90 s later.
The summary, the first file bar, the first diff line and the last file bar always land
in the same frame: the page waits for the whole comparison, then projects every file
section at once. On the stress case that one projection is a 593 ms task on the main
thread, and the five long tasks together block 666 ms.
The 1,183 bars are 1,133 empty bodies and fifty with lines, 43,788 DOM nodes (80,374 by
Chrome’s count, which includes text nodes), and 356 ms of layout.

The title and tabs arrive at 0.2–0.35 s whatever the size: the pull route is served from
the record and the header paints before the comparison is asked for.
That part of the design is right.
Everything below it waits for a response whose time is the whole pull request’s.

Conversation, same method:

| Pull request | Load | Title | Body, plain | Body, Markdown | LCP | Long task max | DOM nodes | Transferred |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 3 files | 8 | 215 (190–227) | 215 | 232 | 256 | 59 ms | 1,551 | 686 KB |
| 42 files | 15 | 350 (283–397) | 350 | 367 | 388 | 66 ms | 2,008 | 704 KB |
| 17 files | 20 | 395 (366–545) | 395 | 458 | 444 | 0 | 1,749 | 693 KB |
| 1,183 files | 39 | 288 (284–526) | 288 | 350 | 328 | 0 | 1,584 | 695 KB |
| 101 files, +442k | 28 | 685 (401–2,501) | 685 | 969 | 716 | 0 | 1,363 | 620 KB |
| 663 files | 24 | 258 (215–266) | 258 | 283 | 304 | 0 | 1,317 | 597 KB |

Conversation is independent of the pull request’s size, as it should be; the one
outlier, 2.5 s on a run of the giant-additions case, was taken at a load average of 36
while another process held the machine.
Its 0.2–0.4 s is the shell: 62 requests, 875–925 KB transferred and 4.6 MB decoded for a
Files changed page, of which 50 scripts are 415 KB on the wire and 1.4 MB decoded, four
stylesheets 81 KB, and `/api/catalog`, the whole repository’s file catalog for the
search palette, 176 KB on the wire and 1.9 MB decoded, fetched on a page that is about
one pull request.
None of it is on the comparison’s critical path; all of it is parsed on
the main thread before the reader has asked for anything.

Unified layout, two runs each: the 42-file case painted its first diff line at 745 ms
(643–847) against 685 in split, with 8,996 DOM nodes against 9,882; the stress case at
6,654 ms (6,053–7,255) against 8,026, 38,786 nodes against 43,788, load 45 against 30.
The layout is not what the time is made of.

Server memory: 105–124 MB RSS after serving the small and medium cases, 350–390 MB after
the stress case. The 14.8 MB patch, its parse and its 16 MB document are built and
dropped per request, and the interpreter keeps the high-water mark.

## Interaction

The same runs, after settle, trusted input, Event Timing durations (what INP would
report) and Long Tasks.
Load 9–30.

| Pull request | Scroll: longest frame gap, dropped frames | Split to Unified: event, full projection | Collapse a file: event | Conversation tab | Back to Files changed: first diff line | Open a file from its bar |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 3 files | 10 ms, 0 | 44 ms, 50 ms | 24 ms | 37 ms | 141 ms | 402 ms |
| 42 files | 9 ms, 0 | 96 ms, 156 ms | 24 ms | 60 ms | 373 ms | 348 ms |
| 17 files, long | 12 ms, 0 | 72 ms, 121 ms | 24 ms | 64 ms | 441 ms | 493 ms |
| 1,183 files | 34 ms, 12 | **264 ms, 444 ms** | 40 ms | 239 ms | **12,124 ms** (5,685–12,533) | 514 ms |
| 101 files, +442k | 9 ms, 0 | 176 ms, 295 ms | 24 ms | 91 ms | **6,825 ms** (4,421–7,808) | 286 ms |

- Scrolling the hydrated files is clean: no long task, no gap over 13 ms on the medium
  cases, and 12 dropped frames on the stress case’s 43,788 nodes.
- The layout toggle is the batched reprojection
  [the diff-layout benchmark](../../diff-layout/README.md) measured: 96 ms on 42 files;
  on 1,183 sections it is a 264 ms input and two long tasks of 256 and 137 ms, over the
  200 ms the repository budgets, because the 1,133 empty sections are reprojected too.
- Back is the worst number on the page after the first load: a same-document return to
  Files changed mounts the diff view again, which fetches the comparison again, and the
  server computes it again.
  12 s on the stress case, 0.4 s on the 42-file case.
  Nothing about the page changed in between.
- Opening a file from a bar is a full navigation to `/view/`, 0.35–0.5 s to a painted
  view, and independent of the pull request.

## Jumping to a file, and holding a key

Readers will move through a pull request’s files by keyboard from a changed-files list,
which does not exist yet, so the cost underneath it was measured on Files changed
directly: a jump to file N is `scrollIntoView` on the file’s section, which is what a
list’s row would do, and a held key is a jump to the next section every 33 ms, about
thirty files a second, for ninety files.
The clock runs from the jump until the file’s bar is on screen and until its first lines
are painted; afterwards the bar’s position is sampled every 100 ms until the page is
still, to see how far the target moves as its neighbours hydrate.
Two runs per condition, load average 32–109; the times are rough, the counts are not.

| Condition | Jump to a hydrated file: bar, lines | Jump to a deferred file mid-way: bar, lines, hydrations it queued, settled | Jump to the last file: bar, lines, target drift |
| --- | ---: | ---: | ---: |
| 1,183 files, stable | 3–4 ms, 3–4 ms, no request | 5–16 ms, **12.7–22.7 s**, 8–10 queued at 9–17 s each, not settled in 60 s | 2–18 ms, **never in 60 s** behind 7–11 queued neighbours, 0 px |
| 1,183 files, hack | 1–2 ms, 1–2 ms | 14–15 ms, **151–156 ms**, 24 at 29–49 ms, settled 3.5 s | 1–14 ms, 1.8–2.2 s, **53,661 px: pushed off screen** |
| 42 files, stable | 1–5 ms, 1–5 ms | all files hydrated | 1–2 ms, 1–2 ms, 0 px |
| 1,031 files public, stable | 2–15 ms, 2–15 ms | 2 ms, **4.6–5.7 s**, 16–19 queued at 5.5–9 s each, not settled in 60 s | 25–28 ms, never in 60 s, **65,535–85,414 px: pushed off screen** |
| 1,031 files, github.com | 0.37–0.41 s, loaded | 1.05–1.18 s, never: not loaded on the logged-out page | 1.5–1.6 s, never, the 1,288–168,118 px is its own smooth scroll |

| Condition | Held key, 90 files at 30/s: time held, hydration requests, in flight at key-up, settled after key-up, long tasks (max, total), dropped frames |
| --- | --- |
| 1,183 files, stable | 4.0–4.1 s, 19–20 requests at 12.3 s median, 2 in flight and 17 waiting, **not settled 120 s later**, 1–2 (54 ms, 80 ms), 101–161 |
| 1,183 files, hack | **11.0–11.8 s to deliver 90 steps**, 101–103 requests at 18 ms median, 2 in flight, settled 5.9 s later, **87–88 long tasks (254 ms, 11.2 s)**, 723–744; DOM 43,788 to 121,861 |
| 42 files, stable | 1.5 s for 40 steps, 0 requests, settled 2.0 s, 0, 0 |
| 1,031 files public, stable | 4.9–5.5 s, 35–44 requests at 6.3 s median, 2 in flight, **not settled 120 s later**, 54–59 (**527 ms**, 14.6–18.5 s), **4,457–4,580**; DOM to 261,271–269,961 |
| 1,031 files, github.com | 2.2–2.5 s for 45 steps, 0 requests, settled 2.1 s, 25–30 (86 ms, 1.5–2.0 s), 129–173 |

What this says:

- **The bar is instant; the lines are the route.** On the stable build a jump lands on
  the file’s bar in under 20 ms whatever N is, because every bar is in the DOM. Its
  lines arrive when its hydration request answers: at once for the first fifty files,
  after one whole-comparison recompute (4.4 s quiet, 9–23 s under this load) past them,
  and behind every neighbour that reached the viewport first, since the queue is
  first-in-first-out and two wide.
  A jump to the last file never showed its lines within a minute.
- **The public 1,031-file pull request shows the stable build’s page as the bottleneck
  too, without any hack.** Its files are large, so each hydration the traversal queued
  rendered a big section: 54–59 long tasks up to 527 ms, 14.6–18.5 s of blocked time,
  four and a half thousand dropped frames, the DOM grown from 114,601 to 269,961 nodes,
  and the last-file jump pushed 65,535–85,414 px off screen by its neighbours.
  The route makes it slow; the page’s shape makes it unresponsive.
- **A fast route moves the problem into the page.** With hydration at 30 ms the mid-way
  jump paints its lines in 150 ms.
  But every empty bar the jump brought into view hydrates too, 24 of them, and the
  target of a jump near the end, which cannot sit at the top of the viewport, is pushed
  53,661 px down the page by the sections above it filling in.
  Chrome’s scroll anchoring holds the node at the top of the viewport, not the one the
  reader asked for.
- **A held key on the stable build leaves a queue that outlives the key by minutes.**
  Ninety files passed at thirty a second queued twenty hydrations of 4.4 s each, two at
  a time; at key-up two were in flight and the rest were waiting, and two minutes later
  the page was still filling in files the reader had left.
  With the hack the same traversal issued 102 requests and rendered 102 files on the
  main thread, 88 long tasks and 11 s of blocked time, so the thirty-a-second key repeat
  itself stretched to eight a second: the input waits behind the rendering it caused.
- **GitHub, logged out, cannot jump to a file it has not loaded** and takes 0.4–1.6 s to
  scroll to one it has, its own smooth scroll over 143,853 nodes; its held key issues no
  requests and drops 129–173 frames.
  The jump it offers signed in, through its file tree, loads the file first; that run
  belongs in the owner’s browser.
- The 42-file case is the shape everything should have: every jump 1–5 ms, a held key
  through all forty files with no request, no long task and no dropped frame.

Proposed budgets, measured beside each:

| Metric | Budget | Measured now | Reasoning |
| --- | --- | --- | --- |
| Jump to any file N: bar on screen | 50 ms | 1–18 ms | met; the bar is in the DOM |
| Jump to any file N: first lines painted | 150 ms | 3 ms to never | one path-limited diff is 13 ms, the hack’s cache hit 3 ms, and one file’s projection is under 10 ms; GitHub’s own loaded-file jump is 0.4–1.6 s |
| Target drift after a jump | 0 px | 0 to 53,661 px | the reader asked for that file |
| Held key at 30/s: input delivered at the key’s rate | 33 ms per step | 45 ms stable, 127 ms hack | no step may wait behind rendering |
| Held key: requests in flight | 1, for the file the key rests on | 2 plus 17 waiting | the reader did not ask for the files passed |
| Held key: queued work after key-up | the resting file only, settled within 300 ms | 120 s stable, 5.9 s hack | nothing the reader left behind should keep running |
| Longest task during traversal | 50 ms | 54 ms stable, 254 ms hack | the responsiveness invariant: main-thread work per task bounded by a constant |

To meet them the page has to change shape, not speed: hydrate the file the reader is on,
not every empty bar that crosses the viewport, so a jump requests one file and a held
key requests the file it rests on after a short debounce and cancels the rest; hydrate
the jump target first, ahead of anything queued; give an empty body a stable height, or
scroll the target to the top of the pane with a spacer below the last file, so nothing
above it can move it; render at most one hydrated file per frame; and, past a few
hundred files, mount only a window of sections around the reader’s position, which is
what a changed-files list makes natural.
The server side of this is fixes 1 and 2 below; without them every budget here is
unreachable, and with them alone the page becomes the bottleneck, as the hack row shows.

## The GitHub baseline

The same pull request’s Files changed on github.com, logged out, and in the stable build
serving a mirror of the same repository from an isolated cache, back to back, two pairs
per pull request, visible Chrome, fresh context per run.
Load average 12–47. Milliseconds from navigation start to the painted frame; medians
with ranges.

| Public pull request | Site | TTFB | Title | First diff line | All file bars | Bodies with lines | Long task max, count | TBT | DOM nodes | Requests, transferred, decoded | Scroll: longest gap, dropped frames |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 36 files | github.com | 800 | 1,609 (1,134–2,084) | 1,609 | 4,537 (2,866–6,208) | 31 of 36, four “Load diff” | 878, 6 | 1,328 | 34,313 | 171, 1.98 MB, 9.9 MB | 442 ms, 39 |
|  | metab | 17 | 229 | **662** (646–678) | **662** | 36 of 36 | 194, 1 | 144 | 17,606 | 67, 644 KB, 2.5 MB | 9 ms, 0 |
| 67 files | github.com | 1,084 | 2,001 (1,293–2,709) | 2,001 | 3,926 (2,151–5,700) | 67 of 67 | 556, 12 | 1,598 | 20,266 | 175, 1.92 MB, 9.2 MB | 212 ms, 20 |
|  | metab | 21 | 442 | **1,046** (904–1,187) | **1,046** | 50 of 67 | 142, 1 | 92 | 17,665 | 71, 644 KB, 2.6 MB | 17 ms, 0 |
| 93 files | github.com | 1,402 | 2,136 (1,986–2,286) | 2,136 | 5,132 (4,970–5,294) | 91 of 93 | 375, 6 | 520 | 18,298 | 175, 1.92 MB, 9.3 MB | 163 ms, 30 |
|  | metab | 22 | 312 | **654** (511–796) | **654** | 50 of 93 | 134, 1 | 84 | 12,881 | 67, 776 KB, 4.0 MB | 9 ms, 0 |
| 301 files | github.com | 3,223 | 4,370 | 4,370 (4,363–4,376) | 14,787 (13,726–15,847) | 129 of 301, progressive | 703, 15 | 2,044 | 63,794 | 185, 2.37 MB, 15.5 MB | 746 ms, 103 |
|  | metab | 56 | 569 | **never: 404** | never | none | 0 | 0 | 1,028 | 68, 585 KB, 2.0 MB |  |
| 1,031 files | github.com | 1,110 | 2,027 | **2,039** (1,789–2,289) | 21,140 (20,924–21,355) | 79 of 1,031, progressive | 951, 15 | 4,382 | 143,853 | 187, 2.61 MB, 26.1 MB | 1,345 ms, 246 |
|  | metab | 30 | 612 | 6,941 (6,436–7,446) | 6,941 | 50 of 1,031 | 1,143, 5 | 1,373 | 114,601 | 81, 929 KB, 5.2 MB | 30 ms, 3 |
| 5,855 files | github.com | 1,092 | 2,056 | never: refused | never | none | 0 | 0 | 958 | 152, 1.71 MB, 6.7 MB |  |
|  | metab | 20 | 569 | never: no merge base | never | none | 0 | 0 | 917 | 60, 615 KB, 2.3 MB |  |

And Conversation, one pair each, load 18–46 with one spike to 111:

| Public pull request | github.com: TTFB, body painted, requests, transferred | metab: TTFB, body painted, requests, transferred |
| --- | ---: | ---: |
| 36 files | 1,576, 2,913, 371, 4.9 MB | 13, **182**, 63, 542 KB |
| 67 files | 1,241, 2,745, 368, 4.9 MB | 34, **352**, 67, 590 KB |
| 93 files | 1,185, 2,391, 373, 5.0 MB | 17, **250**, 64, 756 KB |
| 301 files | 3,704, 4,933, 405, 5.1 MB | 72, **609**, 69, 561 KB |
| 1,031 files | 1,755, 3,053, 379, 5.1 MB | 31, **499**, 58, 738 KB |
| 5,855 files | 2,016, 3,229, 369, 5.0 MB | 21, **300**, 78, 623 KB |

What the bar says:

- **On a pull request the stable build can show, it is clearly faster than GitHub.**
  First diff line 2.4x, 1.9x and 3.3x sooner on 36, 67 and 93 files; all file bars 6.9x,
  3.8x and 7.8x sooner; Conversation 5–16x sooner; a third of the requests, a third of
  the bytes, a tenth of the decoded bytes, one long task against six to fifteen, and
  scrolling without a dropped frame where GitHub drops 20–246. Every pair, not only the
  medians, had the same sign.
- **On the 1,031-file pull request it is 3.4x slower to the first diff line, and
  GitHub’s first diff line is at the same 2.0 s it shows for 36 files.** GitHub renders
  a page of files and loads the rest progressively, so its first paint does not grow
  with the pull request; the stable build waits 6.9 s for the whole comparison.
  Past that first paint, GitHub’s own page is the worse place to be: 21 s to its last
  file bar, 143,853 nodes, fifteen long tasks, 4.4 s of blocking time, and a 1.3 s
  freeze while scrolling; metab’s 114,601 nodes scroll at 30 ms.
- **On the 301-file pull request the stable build shows nothing** and GitHub takes 4.4 s
  to the first file and 14.8 s to the last.
  The 404 is the parser refusing a section, described under
  [The limits](#the-limits-and-what-they-mean-for-a-reader-of-the-stress-case).
- **On the 5,855-file pull request neither shows a diff.** GitHub refuses it; the stable
  build’s record has no comparison (`no_merge_base`), because that closed pull request’s
  base is not in the mirror and the refresh did not fetch it.
  Not measured further.
- GitHub’s TTFB for a Files changed page is 0.8–3.2 s and for Conversation 1.2–3.7 s,
  from this network; its page is 150–405 requests and 1.7–5.1 MB on the wire.
  That is the budget Metabrowser has to beat: it does, by a wide margin, wherever its
  own route is not the bottleneck.

What is already known about the bar beyond these pairs:

- **GitHub’s data path.** `gh api repos/<o>/<r>/pulls/<n>/files` for the stress case is
  twelve pages of 100 at 1.2–1.6 s each, 16.7 s in sequence, load 7; the diff and patch
  endpoints refuse it: `406 Sorry, the diff exceeded the maximum number of files (300)`.
  GitHub will not give its own API a diff of this pull request at all.
- **GitHub’s page, logged out, as this round’s discovery found it.** On a 1,031-file
  public pull request github.com renders 50 file headers with 2,673 diff lines, seven
  “Load diff” buttons on files it judges large, and four progressive containers that
  load the next files as they scroll into view; on a 36-file pull request, 31 files
  rendered and four behind “Load diff”.
  Its documented limit for a diff is 300 files, and its API’s 406 says so.
  GitHub’s first paint is therefore bounded by construction: it never renders more than
  a page of files, and it tells the reader what it left out.
- The current docs page for these limits was not reachable from this session; the
  figures above are the API’s own message and the page as served.
  Older Enterprise editions of the same page give 300 files per diff and 1 MB of diff in
  a view.

## The limits, and what they mean for a reader of the stress case

`MAX_HYDRATED_FILES = 50` in `builtin_plugins/diff/sidekick.py` and
`MAX_MANIFEST_FILES = 2000` in `diff/adapters/git.py`, with `MAX_PATCH_BYTES = 8 MiB` in
`diff/adapters/patch_file.py` and `GIT_SUBPROCESS_MAX_BYTES = 32 MiB` in `settings.py`:

- **File 51.** It is a bar with an empty body.
  Nothing on the page says so.
  The manifest’s `truncated` flag is false, the summary reads the pull request’s real
  totals, and the 1,133 deferred sections look like collapsed files until one scrolls
  into view, when a delayed-loading box appears and a request for that one file goes
  out: 4.4 s on the stress case, two in flight at a time, so a viewport that shows
  twenty empty bars queues ten rounds of it.
  The record and the diff are honest in the data (`availability: deferred`) and silent
  in the page.
- **File 1,000.** Reachable by scrolling, at 4.4 s a file past the fiftieth, with no way
  to go there directly: the page has no changed-files list, only the whole repository’s
  tree in the left pane, which does not know which files the pull request touched.
  Finding one file among 1,183 is reading 1,183 bars.
- **2,000 files.** Past it the manifest is cut and the page says the change list was
  truncated. None of the subjects reached it.
- **8 MiB of patch.** Past it the parse keeps the sections it reached, 677 of 1,183
  files on the stress case, and the route still asks for only fifty; a file past the cut
  that the reader scrolls to is asked for on its own and parses on its own.
  The bound costs 1.26 s of parsing per request on the stress case and loses nothing a
  reader can see. The route’s refusal of the 663-file case is not this bound; it is the
  deleted empty file.
- **32 MiB of Git output.** The stress case’s whole patch is 14.8 MB; a pull request
  with a 33 MB patch, which the giant-additions case is within a factor of four of,
  would raise `GitOutputTooLargeError` and answer 502.

For reviewing a large pull request the missing changed-files list matters more than any
millisecond here, and the hydration cost is what makes the list’s absence hurt: a list
would let the reader jump, and each jump past file 50 would cost 4.4 s. The other
session’s design for the list depends on this route being cheap per file.

## First principles

The physical lower bound for each stage, and the distance from it.

| Stage | Lower bound | Stable build | Distance |
| --- | --- | --- | --- |
| Start-up, cached pull request, serve mode | read a record and a store: milliseconds; the interpreter’s own start, ~0.5 s | 0.74–0.99 s | small |
| Start-up, refresh of the record | six HTTPS requests in flight together, ~0.4 s; or one GraphQL request | 5.5–6.6 s, ten `gh` spawns in sequence | 10x |
| Pull route | a parsed record in memory | 1–2 ms, 304 in 0.8 ms | at the bound |
| Comparison, first request | `merge-base`, one listing with line counts, the patch of fifty files: ~0.5–1.4 s on 1,183 files, ~60 ms on 42 | 4.4 s on 1,183 files, 170 ms on 42 | 3–5x |
| Comparison, repeat | a cached document: microseconds; or the browser’s own cache | 4.4 s, 170 ms | 1,000x |
| One deferred file | one path-limited diff, 13 ms; or a cache hit | 4.4 s | 300x |
| Manifest at fetch time | zero on the request path, computed when the record is written | not done |  |
| First useful pixel | the record’s header: ~0.2 s with the shell | 0.2–0.35 s | at the bound |
| First diff line | the fifty-file document and one screen’s projection: ~0.1 s after the comparison | the whole comparison plus a projection of every section | grows with the pull request |
| All file bars | 1,183 bars is ~15,000 nodes; a list is cheaper | 43,788 nodes, 593 ms task | 3x, in one task |
| Highlighting | the files on screen | fifty files, serialized after mount, yielding per file: 70 ms total on the stress case | fine as is |

Plainly:

- **Is the time to the first useful pixel independent of pull request size?** The header
  is: 0.2–0.35 s on every subject.
  The first diff line is not: 0.36 s at 3 files, 0.69 s at 42, 0.92 s at 17 long files,
  8.0 s at 1,183, and never at 663.
- **What scales with the pull request but need not?** The manifest computed twice; the
  whole-comparison patch where fifty files are served; the Python parse of 8 MiB where
  354 KB would do; recomputation on every request of an immutable comparison of two
  commit IDs; the same recomputation for each deferred file; and a projection of every
  section, 1,133 of them empty, in one task.
- **What could be precomputed at fetch time?** The manifest with line counts, which is
  the one step whose floor is a quarter second on a big pull request, and the fifty
  leading patches. The refresh already writes the record; the comparison’s endpoints are
  in it.
- **HTTP caching of immutable comparisons.** Both endpoints are full commit IDs.
  The response can be `immutable` with an `ETag`; Back then costs nothing and a reload
  costs a 304.
- **Prefetching Files changed from Conversation.** The record arrives at 0.2 s and names
  the comparison; the tab click comes seconds later.
  The diff view already takes a prefetched payload through `ctx.raw`.
- **Streaming.** With the manifest first and patches after, the bars could paint while
  patches arrive; with the route at 43 ms it is not the first fix.
- **DOM virtualization.** 1,183 sections is a bounded task today (593 ms); a
  changed-files list that mounts the files near the reader’s position would make it
  constant, and is the design the other session is writing.

## Where the budget goes

Rough waterfalls from navigation start, Files changed, split, under load:

**42 files.** Shell and scripts to `DOMContentLoaded` 165 ms; `/api/tree` 163–175; the
pull route at 248–292 ms, header painted 285; the comparison requested at 347, answered
at 808 (461 ms, 166 of it server work on a quiet machine); validate 5 ms, projection 16
ms, attach 1 ms; first diff line painted at 685 ms in the median run; syntax
highlighting 98 ms over the next frames; `/api/catalog` 1.9 MB decoded beside it.

**1,183 files.** The same shell to 216 ms; header at 317; the comparison requested at
1,120 ms and answered at 7,540 (6,419 ms under load 30, 4,397 on a quiet one); validate
9 ms; projection 114 ms into 43,788 nodes; attach 12; the first paint at 8,026 ms, 593
ms of it one task; intraline refinement of fifty files 277 ms, syntax 70 ms, serialized
afterwards. Five polls of the pull route at one-second intervals while the record
refreshes, each a 304.

In both, everything after the header is one request, and the request is the server
recomputing the comparison from scratch.

## Budgets proposed

Measured beside each, per the rule that a bound carries its measurement:

| Metric | Budget | Measured now | Reasoning |
| --- | --- | --- | --- |
| Header and tabs painted, any pull request | 300 ms | 180–395 ms | already met on a loaded machine; the shell is the cost |
| First diff line, any pull request in the cache | 500 ms | 356 ms at 3 files, 8,026 at 1,183; 1,145 at 1,183 with the server fixes alone | the comparison must be independent of size: fifty files’ patch is 26 ms of Git and 35 of parse; GitHub’s first file lands at 1.6–2.1 s on every size it shows; what the server fixes leave, a 611 ms projection of every section, needs the windowed page |
| Comparison route, repeat | 50 ms | 4,412 ms | the hack measured 43 ms serving a 197 KB body from memory |
| One deferred file | 50 ms | 4,376 ms | 13 ms of Git, 3 ms from the hack’s cache |
| Back to Files changed, first diff line | 300 ms | 12,124 ms; 529 with the server fixes | an immutable response from the HTTP cache plus the 42-file projection measured at 156–373 ms; the hack’s 107 ms on 42 files meets it, its 529 on 1,183 is the same projection |
| Longest task during load, 1,183 files | 200 ms | 593 ms | the repository’s interaction budget, already applied to the layout switch |
| Layout toggle event, 1,183 files | 200 ms | 264 ms | the same budget; it passed at 1,000 ready files in the diff-layout benchmark and fails with 1,133 empty sections |
| Comparison with a patch over 8 MiB | 200 | 404 | a comparison is not a patch file; the bound must apply per file |
| Record refresh | 1.5 s | 5.5–6.6 s | six requests in flight together on one connection |

## Fixes, ranked by gain for effort

The hack that proves the first three lives in the session scratchpad under `hack/`, as a
copy of `src/metabrowser` with the changes marked `SCRATCH HACK (exp-040)` in
`diff/adapters/git.py`, `builtin_plugins/diff/sidekick.py` and
`builtin_plugins/github/pull-page.js`, run with `PYTHONPATH` ahead of the worktree’s
editable install and gated by `MB_HACK_PATHSPEC`, `MB_HACK_CACHE` and a page cookie so
one build measures both ways.

**Before any of these: a deleted empty file must parse.** `parse_unified_patch` refuses
the section Git writes for one, `diff --git`, `deleted file mode`, `index`, no hunks,
and empties the whole document, and the route turns that into a 404 for the whole
comparison. The 663-file private case and the 301-file public case show no Files changed
for this reason alone.
The fix is in `diff/adapters/patch_file.py`, a deletion with no hunks is a deletion of
an empty blob, and the conformance corpus should hold a case for it.
The hack below happens to load the 663-file case because its first fifty files include
no empty deletion; that is luck, not a fix.
Safe for 0.12.x and the most important line in this record.

1. **Limit the patch to the hydrated files and pass the manifest through** (server,
   `file_patches`). The patch of the fifty served files is 26 ms of Git on the stress
   case against 736, and 354 KB to parse against 8 MiB. Both sides of a rename go into
   the pathspec so Git still pairs them.
   Measured on the stress case, pairs under load 19–23: first request 7.6 s to 2.3 s,
   repeat 8.8 s (6.9–10.6) to 2.5 s (2.2–3.1), one deferred file 12.7 s (8.8–13.9) to
   2.8 s (1.9–3.8). The remaining two seconds are the manifest, still computed on every
   request. The 663-file case loads with this alone, because the patch it parses is 792
   KB. Safe for 0.12.x: it changes which bytes Git produces, not what the route answers.
   Checked: the hacked route’s document, with `resolved`, `manifest` and every hydrated
   patch, equals the stable one on the 42-file, the 101-file and the 1,183-file cases,
   and hydrating one renamed file (similarity 95) and one copied file (similarity 76) on
   demand answers the same single section with the same hunks on both, in 23 and 39 ms
   against 4,925 and 4,983, because both of the change’s paths go into the pathspec and
   Git pairs them. The conformance corpus pins the answer’s shape.
2. **Keep the comparison in memory, keyed by its two commit IDs, and mark the response
   immutable** (server, `comparison_handler`). A comparison of two commit IDs cannot
   change. With the manifest and the hydrated patches kept, a repeat is a serialization:
   43 ms (43–119) on the stress case, 35 ms on the 42-file case, and one deferred file 3
   ms (3–23). `ETag` and `Cache-Control: private, max-age=31536000, immutable` let Back
   come from the browser’s cache.
   In the browser, with fixes 1 and 2 together and the server warm, back-to-back pairs
   under load 14–26: the stress case’s first diff line 6,677 ms (6,260–7,093) on the
   stable build against 1,145 ms (1,022–1,267), its Back 7,422 ms (7,029–7,815) against
   529 ms (502–555); the 42-file case 803 against 620 and its Back 352 against 107. What
   remains of the stress case’s 1.1 s is the page: the 611 ms projection of 1,183
   sections, which the route cannot remove.
   Safe for 0.12.x with a bound on entries; the hack keeps eight.
   The giant-additions case still takes 1.0–1.4 s on a repeat because the response is
   13.5 MB of JSON serialized each time; caching the encoded body, as the rollup route
   already does, would make it tens of milliseconds, and fifty files of 442,000 lines is
   the case where a smaller first page is the real fix.
3. **Prefetch Files changed from Conversation** (browser, `pull-page.js`). The record
   names the comparison at 0.2 s; the hack starts the comparison request then, warms the
   diff plugin’s assets, and hands the payload to the view through `ctx.raw` when the
   tab is clicked. Measured on the Conversation page with a trusted click on Files
   changed, two pairs each, load 14–35: on the 42-file case the first diff line painted
   510 ms (379–641) after the click on the stable build, 312 ms (248–375) on the hacked
   server without the prefetch, and 153 ms (141–165) with it, with no comparison request
   after the click; on the stress case 7,655 ms (7,226–8,083) against 590 ms (557–622),
   the rest being the projection of 1,183 sections.
   Safe for 0.12.x; it spends one request the reader was likely to make, and should
   yield to an interaction rather than queue ahead of one.
4. **Drop `-C`** from the manifest’s two commands, or compute the manifest once at fetch
   time and keep it beside the record.
   Copy detection is ten times the listing on 1,183 files and GitHub does not show
   copies. Dropping it changes what a copied file is called; it needs a decision, not a
   design. Computing the manifest at fetch time removes the last request-path cost that
   scales with the pull request and belongs with the mirror-and-checkout plan.
5. **Apply the 8 MiB bound per file, not per comparison**, and keep the sections the
   parser could model when one fails, so a comparison never comes back empty because of
   one section. With fix 1 the comparison’s patch is fifty files and the bound is rarely
   met; one file over 8 MiB should be deferred with a notice, as a binary is.
   Needs a small design: what the reader sees for that file.
6. **Refresh the record with the six requests in flight together**, or one GraphQL
   query. 5.5–6.6 s to about a second.
   Needs design: `gh.py` deliberately names every page and reads every ETag, and
   parallel calls change how a rate-limit refusal is reported.
7. **Say what is deferred.** A line under the summary, “50 of 1,183 files loaded; the
   rest load as you scroll”, costs nothing and makes the page honest at file 51. Safe
   for 0.12.x.
8. **Do not fetch the repository’s catalog on a pull-request page** until the search
   palette is opened: 1.9 MB decoded and parsed on the main thread of every page.
   It is not on the critical path, which is why it is last.

Fixes 1, 2 and 7 land together in 0.12.x and make the route independent of the pull
request after its first request.
Fix 4’s fetch-time manifest and the changed-files list need design.
The mirror-and-checkout plan on `claude/v012-pr-review-design`
(`plan-2026-11-02-pr-review-mirror-and-checkout.md`, read at `ac340690`) changes where a
store’s objects come from, an overlay borrowing a checkout’s, and relies on this
comparison route answering the same bytes from either; none of the fixes here changes
what the route answers, and a fetch-time manifest would run the same two commands on an
overlay. That plan’s own measurements, `merge-base` at 25–38 ms and `--numstat` at 27–42
ms, were taken on medium pull requests and hold here for those; the stress case is where
they stop holding, and the plan should carry that.
The Pulls tab plan inherits the same route and the same cache, and a tab that opens one
pull request after another is exactly the case for fix 2.

## What this does not say

- It does not give careful wall-clock pair ratios.
  The machine’s load average never fell below 2.5 and was 20–45 for most of the browser
  series; every browser figure is a rough cut and the route figures were taken twice,
  once at load 3–6 and once at 19–35, and agree in direction and in order of magnitude.
- It does not measure a signed-in github.com.
  What a run in the owner’s own browser would add: GitHub’s Files changed for the
  private stress case with its file tree, which the logged-out page does not show on
  these subjects, and the true first-file time with GitHub’s React page rather than the
  server-rendered one a logged-out reader gets.
- It does not run the harness.
  `run.py` measures a served folder’s first rows, and nothing here is a folder.

Owed on a quiet machine, back to back: the stress case’s first diff line on the stable
build against the hack; the 42-file comparison route; the Back figure; the scroll frame
gaps on the stress case; and the record refresh.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
