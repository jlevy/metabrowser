---
type: is
id: is-01m83chvd7pwcehje7ssmf38sk
title: Restore Linux TCP_NODELAY on reserved HTTP listening sockets
kind: bug
status: in_progress
priority: 1
version: 8
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
updated_at: 2026-11-23T05:29:11.275Z
started_at: 2026-11-23T05:07:24.189Z
---
Matched-HTTP browser startup on GitHub-hosted Linux retains a repeated 40–41 ms small-asset header/body gap. A prebound listener created with protocol 0 causes asyncio to skip TCP_NODELAY on accepted Linux sockets. Declare IPPROTO_TCP when reserving the port and test the adopted transport. Verify under the pinned 0.12.0 baseline and release candidate after the fix.

## Notes

Matched HTTP narrowed the original veto to a repeated browser resource delay. In the main series 1 KB and 18 KB scripts took 40–41 ms after headers vs 0–1 ms on v0.12. CPython accept retains the protocol of a reserved socket on Linux, and asyncio calls TCP_NODELAY only for explicit TCP. Staged explicit IPPROTO_TCP plus a regression that compares standard and adopted transports, including strict macOS with 25 passing tests and no skips. Linux confirmation and same-boundary candidate benchmark pending.

Linux strict socket suite passed 25/25 on ed7e1f10. Browser header/body gap fell from 40–42 ms to 0–1 ms, all five candidate absolute budgets passed and the three complete first-row pairs passed the 1.1× careful tolerance. Two controls were refused (32.1% coverage, ENOTEMPTY cleanup), so the release comparison requires five complete pairs on exact PR #733 head 80fb76d. Replacement run 45117924502, preserving all attempted captures and hard gates, is in progress.
