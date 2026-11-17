---
type: is
id: is-01m7m9v3mwpg9rgacw38xp0376
title: Concurrent private-file writers can unlink each other's new temporary
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-17T08:26:42.203Z
updated_at: 2026-11-17T08:26:42.203Z
---
write_private_file_atomic (src/metabrowser/home.py) creates its temporary with O_CREAT|O_EXCL and only then takes its flock in _hold_temporary. In that window a second writer of the same name runs _remove_stale_temporaries, lists the new temporary, wins the non-blocking flock, and unlinks it; the first writer's creation check then sees st_nlink == 0 and raises PrivateStorageError ('replaced while it was being checked'). Seen in CI as tests/test_github_pull_files.py::test_concurrent_same_second_refreshes_keep_distinct_persisted_generations (jlevy/metabrowser#507, run 44044253607, Python 3.12), in a layer whose diff touches none of this code. Possible fixes: skip temporaries younger than a short bound in the sweep, or retry creation under a new name when the fresh temporary is unlinked before it is held.
