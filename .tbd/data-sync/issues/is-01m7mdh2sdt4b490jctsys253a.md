---
type: is
id: is-01m7mdh2sdt4b490jctsys253a
title: Test stubs outside test_github_pulls.py still hold a default-executor thread in asyncio.to_thread(event.wait) (mb-xorh's cause)
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7man9fyy31fp5mmq7xg7ake
created_at: 2026-11-17T09:31:07.949Z
updated_at: 2026-11-17T09:31:07.949Z
---
mb-xorh's cause in the rest of the suite. A test stub that awaits asyncio.to_thread(<event>.wait[, T]) keeps one of the server's default-executor threads for the whole hold. CPython's ThreadPoolExecutor can count an idle thread that is not there (a job submitted while a worker has seen its queue empty but not yet counted itself idle starts a thread; the worker takes the job and the new thread counts itself idle too), so the next job can start no thread and wait behind the held ones. When the test opens the gate only after a request that needs that job answers, it deadlocks (unbounded) or fails at the bound. tests/test_github_pulls.py now uses held_until (polls the threading.Event on the loop, keeps no worker); PR for mb-xorh. Remaining sites, from grep 'to_thread([a-z_.]*\.wait' tests/ on main e442ed10d:
- tests/test_source_freshness_session.py:193
- tests/test_cache_async_locks.py:186
- tests/test_cache_async_locks.py:192
- tests/test_git_process_group.py:298
- tests/test_git_process_group.py:380
- tests/test_git_process_group.py:422
- tests/test_git_process_group.py:495
- tests/test_git_process_group.py:496
- tests/test_git_process_group.py:499
- tests/test_git_process_group.py:667
- tests/test_git_process_group.py:809
- tests/test_git_process_group.py:972
- tests/test_python_inventory_provider.py:704
- tests/test_python_inventory_provider.py:1151
- tests/test_github_pull_files_summary.py:724
- tests/test_source_refresh.py:284
- tests/test_github_checkout.py:1031
- tests/test_github_pulls_panel_session.py:190
- tests/test_cache_update.py:382
- tests/test_browser_rollup.py:592
- tests/test_github_serve.py:215
- tests/test_github_serve.py:268
- tests/test_diff_comparison_cache.py:791
- tests/test_github_pull_page_session.py:261
- tests/test_github_pull_page_session.py:407
- tests/test_rollup_route.py:410
- tests/test_rollup_route.py:447
tests/test_source_freshness_session.py:193 has no bound, the exact shape of the mb-xorh hang. Each needs a look: a gate set by a server worker thread and awaited on the loop is also a pool-on-pool wait. Move held_until to a shared test module when converting them.
