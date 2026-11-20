---
type: is
id: is-01m7wbe5rqnhsgj5d2d46razrk
title: "test_golden_pin_age_groups failed once on CI (Python 3.12): all 7 files in older, as if the patched clock was not in effect"
kind: bug
status: open
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-11-20T11:28:30.998Z
updated_at: 2026-11-20T17:04:05.417Z
---

## Notes

Seen again 2026-11-20 on CI Python 3.13 (unit 3.13, 2/2), run 44771587418 for jlevy/metabrowser PR 645 at 928e94edf merged with main: same signature, [('older', 7)] instead of [('24h', 1), ('older', 6)]. Other interpreters passed; the failed job was rerun.
