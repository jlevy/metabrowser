---
type: is
id: is-01m7m91x7qs2xbsz7kae1ch64n
title: "Flake: test_golden_pull_files_failures saw no account_changed stamp on disk in the command after it (run 44043888346)"
kind: bug
status: closed
priority: 2
version: 6
delegate: claude-code@vm
labels:
  - linear
dependencies: []
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
child_order_hints:
  - is-01m7mbwaw9rhxejyx0z8t1fjby
hold: null
hold_until: null
created_at: 2026-11-17T08:12:56.439Z
updated_at: 2026-11-20T17:00:13.418Z
started_at: 2026-11-17T08:16:02.342Z
closed_at: 2026-11-17T17:48:13.230Z
close_reason: "Fixed by #513 (review A addressed; A1 fixed with the reviewer's own verified form), merged 2026-11-17."
resolution: null
duplicate_of: null
---
Seen once, in unit (3.13, 1/2) of CI run 44043888346 (jlevy/metabrowser#504 at e6f77bfb3; the other seven unit legs and 3 earlier runs passed it): tests/test_cli_github_pull_files_golden.py::test_golden_pull_files_failures failed its golden, cli-github-pull-files-failures.txt, at the command after the account-changed refresh (the gh-missing case, golden line 550).

The test's own asserts on the account-changed refresh passed: the CLI printed, after waiting for the job, last_refresh.outcome account_changed and state stale. But the next metab process, reading the record when it started its refresh, saw state current, last_refresh null, refreshing true, where the golden records stale and account_changed. So the account_changed stamp was not on disk, or was overwritten, between one CLI process and the next.

Where to look: src/metabrowser/builtin_plugins/github/pull_files_refresh.py, refresh_pull_files, which writes the stamp with write_files_refresh after the job, and _write, which logs at debug and drops an OSError writing the list; and whether the CLI prints the envelope before the stamp write has finished. mb-l2yn fixed the same scenario's list state for PR #279.

The module ran whole on one xdist worker, in order (--shard-by=file), as under Phase 1's make test, so this is not a shard-order dependence. Not rerun by the implementing agent; reported to the coordinator.

## Notes

2026-11-17: cause found and fixed in product code, PR jlevy/metabrowser#513 (branch claude/pull-files-stamp-race, head d7acba11d). Cause: pull_files_refresh_handler read the envelope in a worker thread after starting the job; the gh_missing job republished its stamp by atomic rename within microseconds; open_private_file refuses an entry replaced during its check (UNVERIFIABLE, replaced while being checked), and read_refresh_stamp via read_bytes_bounded took that as no stamp, so last_refresh null and state current. Also possible: the read after the job's write shows the job's own gh_missing. Evidence: tight-loop probe 424/50,000 stamp reads None before, 0 after; golden gh_missing step looped: none 1/200 and own stamp 1/200 unloaded, own stamp 6/600 loaded before; 1200/1200 previous stamp after. Fix: PrivateStorageError.replaced + read_bytes_bounded reopens up to MAX_READ_OPENS=4 (measured); the route reads before start_files_refresh and assembles after. Deterministic tests in test_cache_atomic, test_github_pull_files, test_cli_github_pull_files_golden. Follow-up mb-7pu0 for the same post-start read in pulls-refresh. Not closed: coordinator closes on merge.
