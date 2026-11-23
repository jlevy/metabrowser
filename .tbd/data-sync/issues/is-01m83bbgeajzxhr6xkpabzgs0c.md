---
type: is
id: is-01m83bbgeajzxhr6xkpabzgs0c
title: Restore CLI 0.13.0 first directory row below the browser release budget
kind: bug
status: closed
priority: 1
version: 10
refs:
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45112075401
    at: 2026-11-23T04:41:51.934Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45113677625
    at: 2026-11-23T04:48:39.176Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45113917455
    at: 2026-11-23T04:48:39.183Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45116045122
    at: 2026-11-23T05:11:17.233Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45117924502
    at: 2026-11-23T05:29:02.299Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hhr36mmrjwfw662gmgngf6
child_order_hints:
  - is-01m83chvd7pwcehje7ssmf38sk
hold: null
hold_until: null
created_at: 2026-11-23T04:41:44.647Z
updated_at: 2026-11-23T06:05:39.247Z
started_at: 2026-11-23T04:41:48.946Z
closed_at: 2026-11-23T06:05:39.247Z
close_reason: "Independent review, full PR CI 45117784551, and exact post-merge CI 45119777260 passed for #733 (3f132cb3442c0072a2762a93f635ca7133fa4968). The exact five-pair release comparison 45117924502 met all hard budgets and release tolerances. Median first row was 123 ms vs 142 ms, and the Linux socket proof passed 25 tests. Raw evidence and the explained comparator caveats are in exp-102."
resolution: null
duplicate_of: null
---
Five admitted foreground Chrome comparisons put the v0.13.0 candidate at 697–765 ms from navigation to the first directory row, versus 131–242 ms in v0.12.0 and the required 350 ms. The backend first-row median and ordered results match. Attribute the browser-side delay, fix a focused cause with the new startup font work accounted for, then rerun the exact candidate.

## Notes

Matching first successful HTTP response restores all five candidate absolute budgets, and the remaining relative regression is four pairs above the 1.3× rough-cut tolerance. Browser late scripts and DOMContentLoaded shift about 80 ms. Two scripts, including a 1 KB script, take a uniform ~40 ms longer after headers while responding within the same server budget. mb-6cx8 fixes a Linux TCP_NODELAY hypothesis. Combined exact candidate with the narrowed font change is running.

Exact #733 head 80fb76d run 45117924502 reached five complete admitted release pairs and all candidate hard gates passed. First rows 117–159 ms (median 123) vs 135–151 ms (median 142). Ratios 0.956, 0.804, 0.815, 1.120, 0.824; all within the 1.3 release tolerance. Pair 5 is the only careful 1.1 exceedance and does not establish a repeatable regression. One 72.6% control refusal was preserved and replaced by pair 6. Linux adopted-transport suite 25/25, measured JavaScript header-to-body 0–1 ms in complete pairs, and backend ordered rows identical. Stock compare still declines the different KPress locks and automated tallies still report nine intentional differences. All raw evidence retained. Formal PR review and merge gates are tracked separately.
