---
type: is
id: is-01m0t5x6fpbhb2b8y8cczxrtnf
title: Validate merged main cold-start performance against v0.6.0
kind: task
status: closed
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-08-24T15:23:30.165Z
updated_at: 2026-08-24T15:53:44.710Z
closed_at: 2026-08-24T15:53:44.709Z
close_reason: Fetched and rebuilt merged main bae51fd; compared exact v0.6.0 and the installed wheel over five interleaved backend runs plus four fresh-profile headed-browser runs per condition on the same 247,063-file corpus. Main reduced backend first-row and completion medians by about 62%, passed every browser hard gate in all four runs, eliminated observed long tasks and blocking, and reduced median worst input latency from 204 ms to 20 ms. v0.6.0 failed all four browser gates. Verified the trading docs folder overview and README render without request or console errors after a 241,202-file complete index. make verify passed (1,505 tests, 1 skipped, 48 golden checks, audits and distribution smoke clean). Tracked the one overlapping FCP/spawn tail-variance caveat separately.
resolution: null
duplicate_of: null
---
