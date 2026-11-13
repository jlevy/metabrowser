# Research: What Eager Startup JavaScript Costs

**Date:** 2026-11-12

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Complete

## Overview

A folder’s page requests 20 scripts before `DOMContentLoaded`, and
`devtools/check_startup_scripts.py` gates them on every `make lint-check` against
`startup_script_transfer_kb` in
[`performance-budgets.toml`](../../../explorations/performance-loop/performance-budgets.toml).
The check counts each script’s gzip-compressed body plus the 300 bytes Chrome’s
`transferSize` adds per response, and matches Chrome byte for byte (exp-037). The
ceiling was 175 KB, set in August from exp-014’s measured 154 KB plus headroom.
Nothing measured what a kilobyte of it costs.

The ceiling had started to steer code.
The Shift-reveal keyboard work came within 114 bytes of it, dropped `@type` annotations
and trimmed comments in `app.js` to fit, and restored both later at 346 bytes over.
Deleting documentation to satisfy a byte count is worth doing only if the bytes cost
something, so this brief measures the cost and sets the ceiling from it, as
[Agent Instructions](../../../AGENTS.md#browser-and-plugin-boundary) asks: establish the
cost’s shape in a real browser, set the limit at a measured size, and record the
measurement beside the constant.

## Questions to Answer

1. On the paths Metabrowser serves (loopback, and a `metab --remote` SSH tunnel), how
   many milliseconds do the eager bytes cost, split into delivery, parse and compile,
   and evaluation, and how do they move the first tree row and first contentful paint?
2. How much of the eager payload is comments, and would serving the scripts without
   them, with no build step and no new dependency, be cheaper and more honest than
   deleting documentation to fit?
3. What ceiling, and in what unit, follows from measuring before bounding?

## Scope

Included: the folder shell’s 20 startup scripts on `main` at 27ea216c; cold loads (empty
HTTP cache) and warm loads (HTTP and V8 code caches filled); loopback, and two emulated
SSH links; a 4x CPU slowdown.
A served Git mirror’s pin is also served from the local process, so its page is the
loopback case with one more script (`git-path.js`); it was not measured separately.

Excluded: the vendor prefetch tier, stylesheets, the pull-request shell (which adds
`pull-route.js`), visible-window paint timing, and `WKWebView`, which has no on-disk
bytecode cache
([apparent UI performance](research-2026-11-11-ui-apparent-performance.md)).

## Findings

### The Eager Set Is One-Third Comments

`eager-comments.mjs` tokenizes each script with TypeScript’s parser and counts comment
ranges, so a `//` inside a string or a regular expression is not counted:

| Measure | Bytes | Share |
| --- | ---: | ---: |
| Decoded script | 602,780 |  |
| Comments | 190,325 | 31.6% of decoded |
| JSDoc blocks (`/** … */`) | 71,395 | 11.8% of decoded |
| One-line type annotations (179 `/** @type {…} */`) | 6,700 | 1.1% of decoded |
| Transferred, as the check counts it | 178,592 |  |
| Transferred with every comment removed | 104,937 | 58.8% of `main`’s |

Prose compresses worse than code, so removing the comments cuts 73,655 of the 178,592
transferred bytes, 41%, although they are 32% of the decoded ones.
It takes `app.js` from 90,390 to 49,596 compressed bytes, `navigation.js` from 11,593 to
6,464, and `tree-filter-model.js` from 11,129 to 5,854.

### Where a Byte’s Cost Goes

Chrome streams every one of the 20 scripts: it parses each on a worker thread while it
downloads (`v8.parseOnBackground`), so the main thread only finalizes each script’s
top-level compile. Medians of 30 cold loopback loads of `main`:

| Phase | Where | Time |
| --- | --- | ---: |
| Shell HTML, last byte | network | 17.5 ms |
| Startup scripts, last byte | network | 108.5 ms |
| Parse while streaming, all 20 | worker | 9.4 ms |
| Compile finalization | main thread | 0.3 ms |
| Top-level evaluation | main thread | 16.7 ms |
| Lazy function compiles before the first row (1.2 ms of it parsing) | main thread | 3.3 ms |
| Main thread busy, navigation to first row | main thread | 43.4 ms |
| First tree row inserted |  | 117.7 ms |
| First contentful paint |  | 84.0 ms |

The script window, about 90 ms from the HTML’s last byte to the scripts’, is where the
time goes. Per added kilobyte, the worker parse costs 0.007 ms and the main thread 0.010
ms. Evaluation does not depend on byte count: it varied by under 0.7 ms across builds
that differ by 376 KB of comment.

First contentful paint barely moves with script bytes: the scripts sit at the end of
`<body>`, and the shell paints before they arrive.
The largest paired change, −8 ms (−16 to 0) for the stripped build on loopback, is at
the edge of its noise, and the doubled and 220 KB builds moved it by 0.

### On Loopback the Cost Is the Server’s Compression

The variants (see [Methodology](#methodology)) change only comment bytes, so a paired
difference between them is the cost of bytes alone:

| Build | Transferred | First row, paired against `main` |
| --- | ---: | --- |
| Comments removed | 104,937 | −21.3 ms (95% CI −31.6 to −12.2), 0.82x |
| `main` | 178,592 |  |
| Comments padded to 220 KB | 225,531 | +6.6 ms (+2.8 to +12.4), 1.07x |
| Comments doubled | 261,266 | +9.0 ms (−10.9 to +24.3), 1.08x |
| `main`, sent uncompressed | 608,780 | −32.1 ms (−47.2 to −11.7), 0.77x |

Sending 3.4 times the bytes uncompressed made the first row *earlier*. Bytes over
loopback cost almost nothing; compressing them does.
Starlette’s `GZipMiddleware` compresses each script response as it streams it, on the
event loop, at level 6. Compressing the eager set in-process took 18.2 ms for `main`,
10.5 ms stripped, and 27.2 ms doubled: 0.108 to 0.109 ms per compressed kilobyte in all
three builds, measured on this host under load, and more in wall time when the loop is
serving the other scripts at once.
Inflating the result again takes about 1 ms.
The gate’s unit tracks this cost because compression time is proportional to the
compressed size.

### On a Remote Link the Cost Is the Wire, and Round Trips Matter More

`metab --remote` runs the server on the far host and forwards its port over `ssh -L`, so
every request crosses the link, and `metab` does not ask SSH to compress.
DevTools network emulation reproduces that: added latency per request and a shared
throughput limit.

| Link | First row, `main` | Comments removed | Comments doubled | Uncompressed |
| --- | ---: | --- | --- | --- |
| 10 ms, 100 Mbps (12 pairs) | 128.7 ms | −13.9 ms (−70.5 to +2.1) | +19.8 ms (−63.8 to +55.4) | +20.1 ms (−53.1 to +47.0) |
| 80 ms, 20 Mbps (10 pairs) | 499.2 ms | −20.8 ms (−22.7 to −18.4) | +27.9 ms (+26.6 to +30.4) | +146.4 ms (+143.7 to +148.0) |

Off loopback, compression pays for itself: identity encoding is 1.29x slower on the 80
ms link. The 10 ms series ran at load average 37 to 68 and resolves little beyond its
slope.

On the 80 ms link the scripts’ bytes cost about 56 ms (0.32 ms per KB), but the scripts’
window is about 400 ms.
HTTP/1.1 gives the page six connections, so 20 scripts take four rounds of an 80 ms
round trip, an estimated 320 ms of that window.
There, `startup_script_requests` bounds the larger cost.

### Warm Loads and Slow CPUs Do Not Pay for Bytes

On a warm loopback load of `main`, all 20 scripts came from the HTTP cache and all 20
from V8’s code cache.
The first row was 67.8 ms, and neither removing comments (−1.2 ms, −3.8 to +4.1) nor
doubling them (+0.5 ms, −5.7 to +12.7) moved it measurably (15 pairs).

With the page’s CPU slowed 4x, the first row was 198.6 ms and the main thread was busy
for 184 of them. The scripts arrive while it is still evaluating earlier ones, so their
delivery leaves the critical path: 0.016 ms per KB (−0.03 to 0.10), indistinguishable
from zero. On a slow machine evaluation is the cost, and the byte gate does not see it.

### The Shape of the Cost

Across the four comment-only builds, from 105 KB to 255 KB, the first row grows with
transferred bytes, and no knee is visible:

| Path | First row, `main` | ms per transferred KB (95% CI) |
| --- | ---: | --- |
| Loopback, cold (30 pairs) | 117.7 ms | 0.18 (0.08 to 0.23) |
| 10 ms, 100 Mbps, cold (12 pairs) | 128.7 ms | 0.28 (0.06 to 0.40) |
| 80 ms, 20 Mbps, cold (10 pairs) | 499.2 ms | 0.32 (0.30 to 0.33) |
| Loopback, warm (15 pairs) | 67.8 ms | none: no bytes transferred |
| Loopback, cold, CPU 4x (12 pairs) | 198.6 ms | 0.016 (−0.03 to 0.10) |

Each slope is a paired median within one series: per pair, the doubled build’s first row
minus the stripped build’s, divided by their 152.7 KB difference.
So it is not the difference of the two builds’ medians against `main` in the tables
above, which on the 10 ms link gives 0.22 ms/KB. On loopback the cut below `main`
measured steeper (0.29 ms/KB) than growth above it (0.11 to 0.14 ms/KB). In that series
the stripped build always loaded second of three (see [Methodology](#methodology)), so
the difference may be partly its place; the 80 ms link shows no such difference.
The corpus is small, so these first rows are short, which makes each byte’s share of
them larger than on a big tree.
On the repository-shaped corpus the release gate uses, the worst first row was 317 ms
(exp-035).

## Key Insights

- **The gate measures a real cost, but not the one its name suggests.** On loopback, the
  default path, a transferred kilobyte costs about 0.18 ms of a cold first row, and
  nearly all of it is the server compressing that kilobyte.
  Parse is about a tenth of it, and moving bytes over loopback costs too little to see:
  sending 3.4 times as many, uncompressed, was faster.
- **The bytes the keyboard work fought over were not measurable.** A kilobyte of
  comments costs what a kilobyte of code costs to send, about 0.2 to 0.3 ms of a cold
  load and nothing on a warm one.
  The first-row confidence interval at 30 pairs is about ±10 ms.
  Deleting a kilobyte of documentation bought a quarter of a millisecond.
- **Larger levers sit next to the gate.** Not compressing at all saved 32 ms on
  loopback, more than removing every comment (21 ms).
  On a remote link, a round of six requests costs a full round trip, and 20 requests
  take four.

## Comparison Matrix

Candidate units for the per-commit gate:

| Criterion | Transferred bytes (today) | Decoded bytes | Parse and compile ms | First-row ms |
| --- | --- | --- | --- | --- |
| Tracks the loopback cost (compression) | Yes: 0.108 ms per compressed KB in every build | Partly: comments and code compress differently | No: under a tenth of it | Yes |
| Tracks the remote cost (wire) | Yes | Partly | No | Yes |
| Deterministic | Yes | Yes | No | No |
| Runs in `make lint-check` without a browser | Yes | Yes | No | No |
| Resolves a 1 KB change | Yes | Yes | No: 0.01 ms/KB | No: about ±10 ms at 30 pairs |

## Options Considered

### Option A: Keep 175 KB

**Description:** The August ceiling, exp-014’s 154 KB plus headroom.

**Pros:**
- No change.

**Cons:**
- It corresponds to no cost.
  Its remaining headroom is under a millisecond, and it was already steering
  contributors to delete documentation.

### Option B: Keep the Unit, Set the Ceiling at a Measured Size

**Description:** Hold transferred bytes as the unit, and set the ceiling at a size whose
cost was measured directly: a build padded with comment to that size, loaded against
`main` on each path, whose median first row stays under the careful 1.1x tolerance.
That is the tolerance for a claim about one change; the evidence below supports it only
as a rough cut.

The slopes picked the size to measure.
At 10% of each path’s first row they allowed 64 KB of growth on loopback and 47 KB on
the 10 ms link, so 47 KB over the 174 KB of 27ea216c, rounded down, gave 220 KB. They
are not the evidence for it.
The 10 ms slope is the least certain (0.06 to 0.40 ms/KB), and the direct measurement
disagreed with both link slopes: on the 10 ms link the slope predicted +12.8 ms and the
build measured −0.7 ms, and on the 80 ms link it predicted +14.7 ms and the build
measured +19.4 ms.

The direct measurement, a 225,531-byte build against `main`, with the paired median and
95% bootstrap interval of each:

| Path | Pairs | Load | First row | Ratio |
| --- | ---: | --- | --- | --- |
| Loopback | 30 | 72 to 92 | +6.6 ms (+2.8 to +12.4) | 1.069 (1.030 to 1.138) |
| 10 ms, 100 Mbps | 20 | 67 to 76 | −0.7 ms (−5.2 to +11.3) | 0.993 (0.954 to 1.110) |
| 80 ms, 20 Mbps | 10 | 56 to 68 | +19.4 ms (+16.5 to +20.4) | 1.038 (1.032 to 1.040) |

A replication in
[the pull request’s performance review](https://github.com/jlevy/metabrowser/pull/387#pullrequestreview-5887302245),
on the same host at load average 8 to 19, measured the same comparison at 1.02x, 1.03x,
and 1.09x in three loopback series and 1.05x on the 10 ms link, with two A/A series of
`main` against itself at +1.3 and −1.4 ms.

**This is a rough cut.** Every series ran on a loaded host, each path as one series, and
this round had no A/A series, so under
[the tolerance rule](../../../explorations/performance-loop/README.md#comparing-a-candidate-with-the-previous-release)
it supports the 1.3x rough cut, not the careful 1.1x. The rough cut here is read off the
median pair ratio and its interval: growth to 220 KB is inside 1.3x, and its medians are
under 1.1x, but the intervals reach 1.14x on loopback and 1.11x on the 10 ms link.
The rule itself judges each pair.
On loopback 3 of 30 pairs exceeded 1.3x (1.30, 1.33, and 1.39) and none fell below
1/1.3; on the 10 ms link one pair exceeded it and two fell below.
The rule’s rerun step was not applied to them.
The careful claim needs a quiet host, at least 24 pairs per path in two independent
series, and an A/A series.

**Pros:**
- The constant is a measured size with a stated cost, and the check stays deterministic
  and browserless.
- The measurement names its anchor, 174 KB, so a later reset can tell whether it would
  compound a second increase on the first.

**Cons:**
- The evidence is a rough cut, so the gate does not guarantee that eager growth to the
  ceiling costs under 1.1x.
- The cost includes the server’s per-request compression, about 0.11 ms of every KB. If
  the server stops compressing per request, the measurement changes.
- The ceiling bounds bytes at the shell’s request count.
  Its headroom adds to `startup_script_requests`’s: at 27ea216c, five deferred shell
  tools made startup scripts, about 45 KB and five requests, fit both ceilings, and in
  the review’s replication cost 1.04x and 1.11x on loopback and 1.09x on the 10 ms link.
  Which scripts may be startup scripts is held by a test instead
  (`tests/test_check_startup_scripts.py`).

### Option C: Count Code Bytes Only

**Description:** Exclude comments from the gate’s count.

**Pros:**
- Documentation would never count against the budget.

**Cons:**
- It hides a measured cost.
  Comments are served, and a kilobyte of comment costs the same compression and wire
  time as a kilobyte of code.

### Option D: Serve the Eager Scripts Without Comments

**Description:** Strip comments at serve time, keep every line break so stack traces
keep their line numbers, and cache the result per file identity.

**Pros:**
- Measured: 72 KB less to send, and a first row 21 ms earlier on cold loopback and on
  the 80 ms link, against a `main` that took other places in its pairs (see
  [Methodology](#methodology)). Documentation stays in the source.

**Cons:**
- With no build step and no new dependency, the server needs a JavaScript comment
  stripper of its own.
  Telling a comment from a regular expression or a template string takes a real
  tokenizer. The way to make that safe is a test that parses every shipped eager script
  with TypeScript’s parser, already a locked development dependency, and requires the
  stripped tokens to equal the original’s, as `eager-comments.mjs` does.
- DevTools would show the scripts without comments.
- Once Option E removes per-request compression, the loopback gain shrinks to the parse
  share (about 2 ms); the remote gain stays.

### Option E: Compress Each Static Script Once

**Description:** Keep the compressed body of each `/static/` file in memory, keyed by
its path, size, and modification time, instead of compressing it on every request.

**Pros:**
- The uncompressed run puts the loopback gain near 32 ms of a cold first row, and remote
  links keep their small transfer.

**Cons:**
- A new serving path beside Starlette’s `StaticFiles`, with its own conditional-request
  and range handling.

### Eliminated Options

- **A first-row lint gate:** needs a browser on every commit, and at 30 pairs on a busy
  host it resolves about ±10 ms, which is 35 to 55 KB. `first_row_ms` already gates the
  release on a visible window.
- **A parse-time gate:** parse runs on a worker while scripts stream in, and costs the
  main thread 0.01 ms per KB, too small for any single change to register.
- **Decoded bytes:** neither compression nor the wire is proportional to it, since
  comments and code compress differently.

## Recommendations

Adopt Option B: `startup_script_transfer_kb = 220`, in the same unit, with the
measurement beside the constant as rough-cut evidence.
At 220 KB the gate allows about 46 KB beyond `main` (178,592 bytes at 27ea216c against
225,791 allowed). The keyboard stack, 346 bytes over the old ceiling, fits with its
comments and annotations intact.
Hold the startup set’s membership with a test, not with the ceilings: no script of an
on-demand bundle, the deferred `shell-tools` among them, may be a startup script.

When the eager tier needs to shrink, prefer removing per-request compression (Option E)
and requests over trimming bytes.
Serving the scripts without comments (Option D) is the documentation-preserving byte cut
if remote links come to matter.
Re-derive the ceiling after either lands, since each moves a slope this derivation used.

## Next Steps

- [x] Set `startup_script_transfer_kb` to 220 with the measurement recorded beside it
- [x] Commit the samples and the interval computation
  ([exp-084](../../../explorations/performance-loop/experiments/exp-084-eager-startup-script-cost.md))
- [x] Hold every on-demand bundle out of the startup set with a test
- [ ] Re-measure the 220 KB build on a quiet host, in two series per path with an A/A
  series, for the careful 1.1x (`mb-djo1`)
- [ ] Compress each static script once and re-measure the loopback slope
- [ ] Decide whether `startup_script_requests` should be set from the round-trip cost on
  a remote link, as this did for bytes

## Methodology

**Host and browser:** Apple M1 Pro, 10 cores, Darwin 25.5, headless Chrome 152.0.7977.83
over the DevTools Protocol, 1280x900. The host was shared and loaded throughout
(1-minute load average 32 to 109), so timings are paired differences between
back-to-back loads, and each interval is a 95% bootstrap interval of the median paired
difference or ratio (5,000 resamples).
Each path is one series, and no series compared `main` with itself, so the results are a
rough cut by the loop’s tolerance rule.
A quiet host would shorten every timing and the loopback compression cost with them, so
the slopes here are on the high side.

**Order:** the order of a pair’s loads reversed every other pair.
That balances two builds, so the 220 KB validations and the uncompressed loopback series
are balanced; in the latter the first load of a pair was 14 ms slower than the second,
which pairing cancels.
It does not balance three or more: in the three-build series the stripped build always
loaded second, and in the four-build series the stripped and doubled builds never loaded
first or last. Comparisons of those with `main` carry any effect of place.
The probe now rotates the order by one each pair and records each load’s place.

**Samples:** every load’s record is committed with
[exp-084](../../../explorations/performance-loop/experiments/exp-084-eager-startup-script-cost.md),
and `tier-probe.mjs --summarize` prints this brief’s first-row differences, ratios, and
slopes from them.

**Builds:** `src/metabrowser` at 27ea216c, copied once per build and served by the
checkout’s `metab` with that copy first on `PYTHONPATH`, over the same 468-file folder
(this repository’s `docs/`, `src/`, and `README.md`, no Git directory).
`eager-comments.mjs` wrote the stripped build, the doubled build (each comment followed
by one of the same kind and length, of prose drawn in order from `cat docs/*.md` at
27ea216c), and the 220 KB build (the same, with `--fraction 0.54`), and checked that
each build’s tokens equal `main`’s. The uncompressed build is `main` with its one
`Middleware(GZipMiddleware, ...)` entry removed from `server.py`’s middleware list.
`devtools/check_startup_scripts.py` measured every build’s transferred bytes.

**Loads:** `tier-probe.mjs`, extended for this round with `--network`, `--cpu`, and
`--warm` and with the startup-script cost split from each load’s trace.
The comparisons with the stripped, doubled, and uncompressed builds ran on the same code
before it moved into the probe, which summed the same trace events under some other
field names; the warm and 220 KB series ran on the probe itself.
Cold loads used a fresh browser context each; warm loads used the default profile after
three loads of each build.
Links were DevTools emulation: 10 ms with 100 Mbps down and 20 Mbps up, and 80 ms with
20 Mbps down and 5 Mbps up.
The first row is when `#tree-content` first holds a row, from a mutation observer.

**Not established:** a visible window’s paint timing, `WKWebView`, a real SSH tunnel
(emulation adds latency per response rather than modeling TCP), the pull-request and pin
shells, and the repository-shaped corpus.

## References

- exp-014 (`explorations/performance-loop/experiments/`): the 154 KB measurement the 175
  KB ceiling was set from
- exp-037: the startup-script check agreeing with Chrome byte for byte
- exp-035: first rows on the repository-shaped corpus
- [Apparent UI performance](research-2026-11-11-ui-apparent-performance.md): the cold
  landing chain and revalidation
- [The cost of JavaScript in 2019](https://v8.dev/blog/cost-of-javascript-2019)
  (official, V8): script streaming and off-thread parsing
- [Code caching for JavaScript developers](https://v8.dev/blog/code-caching-for-devs)
  (official, V8): when the code cache is written and used
- [Resource Timing](https://www.w3.org/TR/resource-timing/) (W3C): `transferSize`
- [GZipMiddleware](https://www.starlette.io/middleware/#gzipmiddleware) (official,
  Starlette): per-response compression

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
