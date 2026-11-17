---
type: is
id: is-01m7mbwaw9rhxejyx0z8t1fjby
title: "pulls-refresh answers race the job's first write: the 202 can show the job's own outcome (latent flake in test_golden_pull_list_failures)"
kind: bug
status: closed
priority: 2
version: 4
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7m91x7qs2xbsz7kae1ch64n
hold: null
hold_until: null
created_at: 2026-11-17T09:02:19.529Z
updated_at: 2026-11-17T17:48:13.637Z
started_at: 2026-11-17T09:04:47.711Z
closed_at: 2026-11-17T17:48:13.636Z
close_reason: "Fixed by #513 (review A addressed; A1 fixed with the reviewer's own verified form), merged 2026-11-17."
resolution: null
duplicate_of: null
---
Found while fixing mb-kq72 (branch claude/pull-files-stamp-race). The pulls-refresh route (sidekick.pulls_refresh_handler) reads the list envelope in a worker thread after it starts the job, as pull-files-refresh did, so the 202 answer races the job's first write. With no gh, the list job writes its gh_missing stamp almost at once, and test_golden_pull_list_failures (tests/test_cli_github_pulls_golden.py, the gh_missing post near line 500, which the golden records) can then show the job's own outcome in the answer that starts it.

Evidence: a scratch loop of that gh_missing post (attic/kq72/test_zz_kq72_pulls_scratch.py in the kq72 worktree) beside six busy loops on a 4-CPU container: the 202 answer showed the job's own stamp in 5 of 400 rounds, the previous stamp otherwise. The mb-kq72 fix already removes the other half (a read during the stamp's rename reading no stamp at all), since it is in read_bytes_bounded.

Fix as mb-kq72 did for pull-files-refresh: read what the envelope is built from before start_refresh, and assemble it after with refreshing as of the start, plus a test whose job writes its stamp as it starts. pull_refresh_handler and the labels and stacks refresh handlers read after the start too; check each for a job that can write before the read.

## Notes

2026-11-17: folded into PR jlevy/metabrowser#513 as commit ba08475da (branch claude/pull-files-stamp-race, head ba08475da). pull_list_route splits pull_list_envelope into read_list (blocking) and list_envelope (no file read); pulls_refresh_handler reads before start_refresh and assembles after, refreshing as of the start, nothing awaited between. Deterministic test: tests/test_cli_github_pulls_golden.py::test_a_started_refresh_answers_with_the_list_as_its_job_found_it writes the job's stamp as it starts; it fails with the read after the start (shows gh_missing). Loop of the golden's gh_missing step under six busy loops: own stamp 5/400 before, previous stamp 350/350 after; list failures golden prefix up to its root-only chmod case matched 8/8 under load. pull-refresh, labels-refresh, stacks-refresh still read after the start; no flake seen there; not changed. Not closed: coordinator closes on merge.
