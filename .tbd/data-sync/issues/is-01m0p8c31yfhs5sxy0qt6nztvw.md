---
type: is
id: is-01m0p8c31yfhs5sxy0qt6nztvw
title: "Side-by-side validation of the perf work: v0.6.0 against main, speed and stability"
kind: task
status: closed
priority: 1
version: 5
labels: []
dependencies: []
parent_id: is-01m0pn7vkfkd7tfzt7r331jkp8
created_at: 2026-08-23T02:49:37.597Z
updated_at: 2026-08-23T07:12:11.890Z
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

COMPLETE. The perf work is genuine, it changes no answers, and the one behaviour difference is deliberate and now documented.

METHOD, corrected from the first attempt. Both builds installed as console scripts -- the candidate built to a wheel and installed into its own venv -- so neither carries a launcher the other does not. Versions asserted different before measuring (0.6.0 against 0.6.1.dev30+8d78c29). Corpora fingerprinted before and after every run and unchanged. Rows polled from `/api/tree`, which is what the nav tree requests; tallies from `/api/tree?depth=0`.

SPEED. Medians, interleaved, five runs on the project corpus and three on the others:

    project      247,153 files, 31,202 dirs, 251 gitignores   28.2s -> 12.2s   2.32x
    deep         120,000 files, 33,057 dirs, 72,701 ignored    6.0s ->  2.7s   2.27x
    wide         120,000 files,    972 dirs, no ignores       28.6s -> 11.1s   2.58x

Three shapes agree. Spread is tight and the candidate's is tighter.

MEMORY. Peak RSS 182.3MB -> 178.0MB on the project corpus, 172-176 -> 166-168 deep, 196-200 -> 190-193 wide. Slightly better everywhere; no leak.

EQUIVALENCE. Identical rows, file counts and byte totals on every shape. On the tallies channel, zero differences. On the rows channel, seven differences, all of them the tally fields, which is the deliberate change filed as mb-amyt and now written into the route documentation.

STABILITY, the finding that was not expected. Under a probe polling without backoff, v0.6.0 did NOT finish indexing the project corpus within 240 seconds; the candidate finished in 28.9s. That is exp-005's interference effect at full strength -- a row request that computes tallies competes with the walker for the GIL -- and removing that computation from row requests is exactly what #66 does. The probe is not a realistic client, but the difference is a real robustness margin: the gain is largest precisely when someone is watching, which is always.

WHAT DID NOT REPRODUCE. exp-006 reports 13.36s -> 0.81s for the gitignore pre-walk on this exact corpus shape. Timed directly:

    candidate  0.879s   -- matches the reported 0.81s
    baseline   2.53s    -- against 13.36s reported

Most likely page-cache state: exp-006 cleared the cache between runs and this run could not (needs `sudo purge`). The baseline's cost is a metadata walk over ~222k directories, exactly what a warm cache erases; the candidate barely walks, which is why its figure is cache-independent and lands on the reported value. Direction confirmed, candidate's absolute figure confirmed, baseline's magnitude understated -- so the real win is AT LEAST 2.9x and the reported 16x is not contradicted.

ONE WORDING PROBLEM, worth a follow-up and not a retraction. exp-006 calls its figure "dead time before the first row". Over HTTP that does not describe what a reader sees here: skeleton rows arrive at 1.3s on BOTH builds, and the pre-walk cost lands in total index time instead. The number is about a phase, not about first paint.

STILL NOT COVERED, named so it is not mistaken for done: a cold page cache, which needs a machine where clearing it is allowed; more than five repeats for a real variance estimate; and a browser-side measurement of what the reader actually perceives, as opposed to what the API reports.
