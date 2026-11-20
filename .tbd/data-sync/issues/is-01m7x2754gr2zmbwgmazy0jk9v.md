---
type: is
id: is-01m7x2754gr2zmbwgmazy0jk9v
title: "test_golden_pin_age_groups puts the tip's 3-hour-old file in Older on some runs: the age bucket comes from an instant other than the patched one"
kind: bug
status: open
priority: 1
version: 2
labels:
  - testing
dependencies: []
created_at: 2026-11-20T18:06:38.217Z
updated_at: 2026-11-20T18:07:04.115Z
---
PR #659 (docs and config only), run 44779638432, job admitted-git (2.56.1): tests/test_cli_git_pin_golden.py:716 got [('older', 7)] instead of [('24h', 1), ('older', 6)], with ages state ready, 7 of 7 dated. The same test passed on 2.50.1 in that run, and on all three admitted Gits in main's run 44780960780 (ca24c5fef, which contains #652). The fixture's commit times are fixed (AGES_TIP = 1588291200) and the test patches content_routes._request_instant to AGES_TIP + 3 h, so the tip file can only land in Older if its bucket was cut at a later instant, such as real time. Unconfirmed hypothesis to test first: a bucketing or derived-value cache keyed by tree OID outlives the test. ages_origin's fast-import stream is deterministic, so every test that uses it has the same tree OID, and a test that dates the same tree at real time (test_golden_pin_file_ages) would leave buckets that this test then reads, depending on xdist order. Reproduce by running the two tests in that order in one process.

## Notes

2026-11-20: test_golden_pin_file_ages then test_golden_pin_age_groups, one process, no xdist, local Git 2.56.1: both pass, so that pairing alone does not reproduce it. Next: run the module and the whole admitted-git selection (make test-admitted-git's list) under xdist with several seeds and record which test ran before the failure on its worker.
