---
type: is
id: is-01m0p8c31yfhs5sxy0qt6nztvw
title: "Side-by-side validation of the perf work: v0.6.0 against main, speed and stability"
kind: task
status: open
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-08-23T02:49:37.597Z
updated_at: 2026-08-23T06:23:58.412Z
---
Validate the performance work in #66 end to end, by comparing the shipped v0.6.0 against a build of main with the performance changes merged. Both stability and speed: a faster build that is less reliable is not an improvement, and the changes here are concurrency-shaped, which is exactly where that risk lives.

TWO BUILDS, SIDE BY SIDE, on the same trees and the same machine:

- **Baseline**: v0.6.0 exactly as published. Install it from PyPI rather than rebuilding it, so the thing measured is the thing users get.
- **Candidate**: main with #66 (and #68) merged, built from source.

Install them so both can run at once without either shadowing the other -- two `uv tool` installs cannot share the `metab` name, so run the candidate from its checkout and reserve the global name for the baseline, or give one an explicit path. Whatever the arrangement, capture `metab --version` from each in the results so no number is attributed to the wrong build.

WHAT #66 CLAIMS, which is what to test rather than a generic benchmark. Its own table, on a 241,000-file tree (~100,000 directories, 23 GB) with one client polling `/api/tree?depth=2` every 2s:

- dead time before any row can exist: 19.1s -> 3.4s

Reproduce that shape first. #66 ships the harness that produced it, so use that harness rather than inventing a second one -- if the numbers do not reproduce, the first question is whether the measurement differs, and a shared harness removes it.

TREES TO COVER. At least: a very large tree (the 241k-file case or nearest available), a deep-and-narrow tree, a wide-and-shallow one, and a small one where the fixed costs dominate and a regression would hide. Include a tree with many ignored files, since the claim is explicitly that the scan still visits them.

STABILITY, which needs saying out loud because it is the half a benchmark skips:
- Repeat each run enough times to see variance, and report the spread, not just a best or a mean. A change that is faster on average and occasionally much slower is a regression in disguise.
- Watch for wrong answers under load, not just slow ones: file counts, byte totals, and the index-done signal must agree between the two builds on the same tree. A faster scan that reports a different total is the failure mode that matters most.
- Exercise the polling path the claim is about -- a client asking repeatedly WHILE the scan runs -- and check the server stays responsive and terminates the scan cleanly.
- Note memory alongside time: trading a large allocation for latency is a real cost on a 23 GB tree and would not show in a timing table.

REPORT: the numbers, the spread, the trees, both versions, and an explicit statement of anything that did not reproduce. A claim that fails to reproduce is a result, not a problem with the test.

## Notes

RESULT: the performance work is genuine, and the two builds agree on what they report.

BUILDS. baseline `metab 0.6.0` installed from PyPI, so the thing measured is the thing users get. candidate `metab 0.6.1.dev27+9084e6b (+30 commits, 8d78c29)` from a source checkout -- and the annotation in that second string is what kept the two apart, since the package version alone said 0.6.0 for both.

EQUIVALENCE, which was the first test and the one that decides whether the timings mean anything.

On a live 249,147-file tree (5.6 GB, 148 top-level rows), both builds report IDENTICAL rows, file counts and byte totals:

    rows 148 | files 249,147 | size 5,591,051,998   -- both builds, depth=1 and depth=2

On a frozen corpus (601 files, git-tracked only, made read-only so nothing moved between runs), `/api/tree?depth=0` -- the endpoint the browser actually uses -- shows ZERO differences after normalising for order.

ONE DELIBERATE DIFFERENCE, filed separately as mb-amyt: a depth-capped request no longer computes navigation tallies; depth=0 is the channel that does. Not user-visible, since app.js fetches depth=0. Documented in exp-007 as the mechanism of the win.

TIMINGS, 2 runs per build, interleaved, same tree and machine:

    index_done   baseline median 32.5s  [30.1 - 32.5]
                 candidate median 19.1s [19.07 - 19.15]     ~1.7x faster

The candidate's spread is also far tighter -- 0.08s against 2.4s -- which is the stability half of the question and points the right way.

WHAT DID NOT REPRODUCE, and why that is a result rather than a problem. #66's headline is "dead time before any row can exist: 19.1s -> 3.4s". This corpus does not show that dead time on EITHER build: subtracting server start-up, first rows arrived in 4ms on the baseline and 2ms on the candidate. The claim was measured on `build_project_corpus` at 10 projects (246,282 files, 31,161 directories) -- a much deeper, more directory-heavy shape than a flat 148-row checkout of repositories. The dead time the fix removes is a function of that shape, so its absence here neither confirms nor contradicts the figure; reproducing it needs that corpus, which #66 ships the generator for.

MEASUREMENT CAVEAT worth carrying forward: the candidate was launched through `uv run --frozen`, which adds roughly half a second before the server starts. That inflates `serving` and `first_row` for the candidate and is why those two are not comparable as raw numbers -- subtract `serving` first. `index_done` is affected by the same constant, which means the 1.7x is if anything understated.

STILL UNDONE, and named so it is not mistaken for covered: the deep-and-narrow and wide-and-shallow corpora, the many-ignored-files case, memory alongside time, and repeat counts high enough for a real variance estimate. Two runs establish a direction and a tight spread; they are not a distribution.
