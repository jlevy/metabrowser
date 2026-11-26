---
type: is
id: is-01m8bz7s7dx150manw46zzg0n9
title: Carry the ask's kind into every companion refresh job
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-26-pull-request-merge-readiness.md
labels: []
dependencies: []
parent_id: is-01m8bmw4sdejvn3fx7tjgeyvpz
created_at: 2026-11-26T13:03:09.549Z
updated_at: 2026-11-26T13:03:09.549Z
---
A ServedPull refresh decides what to read at job start (_reads, after layer 3's review fix). Two paths still over-read: (1) the session staleness refresh in mirror_refresh.py (request_refresh/_fetch_asked when _companion_stale, i.e. is_stale) is an 'other caller', so a job started because only the status was due reads the record in full if a hold is noted before its turn; (2) a page's ask can set _page_asked and then join a job another caller started, which then reads only what is due, and a start refused with too_many leaves _page_asked set until the page's next ask. Fix by carrying the kind of ask (status, record, reader) through the CompanionRefresh protocol instead of a flag. Found in the layer 3 review of the merge readiness stack.
