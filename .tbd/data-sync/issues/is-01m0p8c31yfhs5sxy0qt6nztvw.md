---
type: is
id: is-01m0p8c31yfhs5sxy0qt6nztvw
title: "Side-by-side validation of the perf work: v0.6.0 against main, speed and stability"
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-08-23T02:49:37.597Z
updated_at: 2026-08-23T02:49:37.597Z
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
