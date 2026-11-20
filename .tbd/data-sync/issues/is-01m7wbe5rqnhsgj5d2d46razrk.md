---
type: is
id: is-01m7wbe5rqnhsgj5d2d46razrk
title: "test_golden_pin_age_groups failed once on CI (Python 3.12): all 7 files in older, as if the patched clock was not in effect"
kind: bug
status: open
priority: 1
version: 5
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
created_at: 2026-11-20T11:28:30.998Z
updated_at: 2026-11-20T17:20:42.362Z
---

## Notes

Seen again 2026-11-20 on CI Python 3.13 (unit 3.13, 2/2), run 44771587418 for jlevy/metabrowser PR 645 at 928e94edf merged with main: same signature, [('older', 7)] instead of [('24h', 1), ('older', 6)]. Other interpreters passed; the failed job was rerun.

Seen a third time 2026-11-20 on CI Python 3.14t (unit 3.14t, 1/2), run 44777918273 job 136432582834, for jlevy/metabrowser PR 602 at 1a2e3258b (a Swift-only change merged with main ab64b5c86, whose own run was green): same signature, ages {'state': 'ready', 'files': 7, 'dated': 7, 'older_than': None}, groups [('older', 'Older')]. The 24h group is absent, so new.py's stamp fell before as_of minus 24h: either as_of was not the patched content_routes._request_instant or new.py's stamp was not AGES_TIP. Three interpreters, so not specific to free-threading. Leads not yet checked: the process-wide file_ages_service and source.derived caches shared with earlier tests in the same xdist worker (the fast-import repo has identical oids in every test), and _GitTimes memo keys built from id(index).
