---
type: is
id: is-01m7mc3my1hb6ax05y8wxkyg82
title: "A task that spawns Git or gh and outlives its asyncio.run can hang a CLI's exit on Python 3.12 (mb-pc9v's mechanism): audit the detached ones"
kind: bug
status: open
priority: 3
version: 4
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
created_at: 2026-11-17T09:06:19.200Z
updated_at: 2026-11-20T17:19:19.444Z
---
mb-pc9v found that on Python 3.12 (gh-119710, fixed in 3.13) asyncio.run's shutdown waits forever for a subprocess whose spawn it cancels before asyncio connected the pipes: _cancel_all_tasks cancels CPython's own BaseSubprocessTransport._connect_pipes task, a pipe stays None, and Process.wait() never wakes. Any task still spawning Git when a CLI's asyncio.run ends can hit it. mb-pc9v fixed the gather in diff/adapters/git.py _list_with_patch. Two candidates remain, found while auditing and not changed there: (1) src/metabrowser/git/repo.py _rediscover_in_background deliberately detaches a task that runs three Git processes; repo_info starts it only for an entry past the TTL whose refs' state is unchanged and that is at least GIT_REPO_INFO_MAX_AGE_S old (git/repo.py repo_info), so only a metab command that runs longer than GIT_REPO_INFO_MAX_AGE_S and asks twice could end its asyncio.run while that task spawns. (2) src/metabrowser/builtin_plugins/github/gh.py _finish handles only TimeoutError and CancelledError around its gather, so a reader that raises (a pipe read error set on the stream) leaves gh unkilled and unreaped and its reader tasks running; git/process.py _run_git uses except BaseException for the same shape. Decide for each whether it can be reached and fix at the cause (await or cancel-and-drain before return), with a test that asserts no task or child is left.

## Notes

2026-11-17: review A on jlevy/metabrowser#514 (finding A5) corrected (1): repo_info starts the background rediscovery only for an entry at least GIT_REPO_INFO_MAX_AGE_S old, not for every entry past GIT_REPO_INFO_TTL_S. The same review found, for reachability: the tests that advance the clock past that age drain or await the task (tests/test_git_repo_identity.py), and its sweep of tasks left at asyncio.run shutdown recorded none in that file; gh.py _finish's gather starts after the spawn has returned, so its gap leaves gh unreaped (a leak) but cannot produce the cancelled-spawn hang.
