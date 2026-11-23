---
type: is
id: is-01m83bbgeajzxhr6xkpabzgs0c
title: Restore CLI 0.13.0 first directory row below the browser release budget
kind: bug
status: in_progress
priority: 1
version: 8
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
updated_at: 2026-11-23T05:29:02.315Z
started_at: 2026-11-23T04:41:48.946Z
---
Five admitted foreground Chrome comparisons put the v0.13.0 candidate at 697–765 ms from navigation to the first directory row, versus 131–242 ms in v0.12.0 and the required 350 ms. The backend first-row median and ordered results match. Attribute the browser-side delay, fix a focused cause with the new startup font work accounted for, then rerun the exact candidate.

## Notes

Matching first successful HTTP response restores all five candidate absolute budgets, and the remaining relative regression is four pairs above the 1.3× rough-cut tolerance. Browser late scripts and DOMContentLoaded shift about 80 ms. Two scripts, including a 1 KB script, take a uniform ~40 ms longer after headers while responding within the same server budget. mb-6cx8 fixes a Linux TCP_NODELAY hypothesis. Combined exact candidate with the narrowed font change is running.
