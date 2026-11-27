---
type: is
id: is-01m8bz7s7dx150manw46zzg0n9
title: Carry the ask's kind into every companion refresh job
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-26-pull-request-merge-readiness.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/909
    at: 2026-11-26T23:58:10.744Z
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m8bmw4sdejvn3fx7tjgeyvpz
hold: null
hold_until: null
created_at: 2026-11-26T13:03:09.549Z
updated_at: 2026-11-27T00:04:01.764Z
started_at: 2026-11-26T22:24:39.294Z
closed_at: 2026-11-27T00:04:01.764Z
close_reason: Merged to main as jlevy/metabrowser#909.
resolution: null
duplicate_of: null
---
A ServedPull refresh decides what to read at job start (_reads, after layer 3's review fix). Two paths still over-read: (1) the session staleness refresh in mirror_refresh.py (request_refresh/_fetch_asked when _companion_stale, i.e. is_stale) is an 'other caller', so a job started because only the status was due reads the record in full if a hold is noted before its turn; (2) a page's ask can set _page_asked and then join a job another caller started, which then reads only what is due, and a start refused with too_many leaves _page_asked set until the page's next ask. Fix by carrying the kind of ask (status, record, reader) through the CompanionRefresh protocol instead of a flag. Found in the layer 3 review of the merge readiness stack.
