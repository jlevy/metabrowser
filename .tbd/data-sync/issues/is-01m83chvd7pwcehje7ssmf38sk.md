---
type: is
id: is-01m83chvd7pwcehje7ssmf38sk
title: Restore Linux TCP_NODELAY on reserved HTTP listening sockets
kind: bug
status: closed
priority: 1
version: 10
refs:
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45113677625
    at: 2026-11-23T05:07:25.162Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45113917455
    at: 2026-11-23T05:07:25.166Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45116045122
    at: 2026-11-23T05:11:19.582Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/733
    at: 2026-11-23T05:28:53.612Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45117924502
    at: 2026-11-23T05:28:58.165Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m83bbgeajzxhr6xkpabzgs0c
hold: null
hold_until: null
created_at: 2026-11-23T05:02:41.062Z
updated_at: 2026-11-23T06:05:39.217Z
started_at: 2026-11-23T05:07:24.189Z
closed_at: 2026-11-23T06:05:39.212Z
close_reason: "Independent review, full PR CI 45117784551, and exact post-merge CI 45119777260 passed for #733 (3f132cb3442c0072a2762a93f635ca7133fa4968). The exact five-pair release comparison 45117924502 met all hard budgets and release tolerances. Median first row was 123 ms vs 142 ms, and the Linux socket proof passed 25 tests. Raw evidence and the explained comparator caveats are in exp-102."
resolution: null
duplicate_of: null
---
Matched-HTTP browser startup on GitHub-hosted Linux retains a repeated 40–41 ms small-asset header/body gap. A prebound listener created with protocol 0 causes asyncio to skip TCP_NODELAY on accepted Linux sockets. Declare IPPROTO_TCP when reserving the port and test the adopted transport. Verify under the pinned 0.12.0 baseline and release candidate after the fix.

## Notes

Matched HTTP narrowed the original veto to a repeated browser resource delay. In the main series 1 KB and 18 KB scripts took 40–41 ms after headers vs 0–1 ms on v0.12. CPython accept retains the protocol of a reserved socket on Linux, and asyncio calls TCP_NODELAY only for explicit TCP. Staged explicit IPPROTO_TCP plus a regression that compares standard and adopted transports, including strict macOS with 25 passing tests and no skips. Linux confirmation and same-boundary candidate benchmark pending.

Linux strict socket suite passed 25/25 on ed7e1f10. Browser header/body gap fell from 40–42 ms to 0–1 ms, all five candidate absolute budgets passed and the three complete first-row pairs passed the 1.1× careful tolerance. Two controls were refused (32.1% coverage, ENOTEMPTY cleanup), so the release comparison requires five complete pairs on exact PR #733 head 80fb76d. Replacement run 45117924502, preserving all attempted captures and hard gates, is in progress.

Exact #733 head 80fb76d run 45117924502 reached five complete admitted release pairs and all candidate hard gates passed. First rows 117–159 ms (median 123) vs 135–151 ms (median 142). Ratios 0.956, 0.804, 0.815, 1.120, 0.824; all within the 1.3 release tolerance. Pair 5 is the only careful 1.1 exceedance and does not establish a repeatable regression. One 72.6% control refusal was preserved and replaced by pair 6. Linux adopted-transport suite 25/25, measured JavaScript header-to-body 0–1 ms in complete pairs, and backend ordered rows identical. Stock compare still declines the different KPress locks and automated tallies still report nine intentional differences. All raw evidence retained. Formal PR review and merge gates are tracked separately.
