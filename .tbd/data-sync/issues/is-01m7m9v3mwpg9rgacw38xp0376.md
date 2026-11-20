---
type: is
id: is-01m7m9v3mwpg9rgacw38xp0376
title: Concurrent private-file writers can unlink each other's new temporary
kind: bug
status: closed
priority: 1
version: 7
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/551
    at: 2026-11-20T17:01:49.846Z
delegate: claude-code@spud10
labels:
  - linear
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-17T08:26:42.203Z
updated_at: 2026-11-20T17:59:50.234Z
started_at: 2026-11-18T03:33:47.227Z
closed_at: 2026-11-18T04:04:08.196Z
close_reason: "Fixed on claude/private-writer-race: a writer creates and locks its temporary under a shared flock on the directory, and a sweep judges other temporaries only under the exclusive one (src/metabrowser/home.py). Deterministic regression and thread/process stress tests in tests/test_cache_atomic.py."
resolution: null
duplicate_of: null
extensions:
  linear:
    id: 063f7f8f-ff4a-405e-ad8a-5af7664257e5
    linked_at: 2026-11-20T17:59:50.233Z
---
write_private_file_atomic (src/metabrowser/home.py) creates its temporary with O_CREAT|O_EXCL and only then takes its flock in _hold_temporary. In that window a second writer of the same name runs _remove_stale_temporaries, lists the new temporary, wins the non-blocking flock, and unlinks it; the first writer's creation check then sees st_nlink == 0 and raises PrivateStorageError ('replaced while it was being checked'). Seen in CI as tests/test_github_pull_files.py::test_concurrent_same_second_refreshes_keep_distinct_persisted_generations (jlevy/metabrowser#507, run 44044253607, Python 3.12), in a layer whose diff touches none of this code. Possible fixes: skip temporaries younger than a short bound in the sweep, or retry creation under a new name when the fresh temporary is unlinked before it is held.

## Notes

2026-11-18 03:09 UTC: hit main. Run 44226931571 at a604716eb (#524 merge), admitted-git (2.43.7): PrivateStorageError 'replaced while it was being checked' writing pull #106's changed files (gh_lists.PullDataError). Coordinator reran the failed jobs once per AGENTS.md's known-flake rule and raised this to P1 for a fix now.
