---
type: is
id: is-01m84x34m2rjmj1ew82cp90aak
title: "Two tests' wall-clock bounds fail under a loaded machine: plugin-collection subprocess timeout and Chrome start counting"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-23T19:10:59.200Z
updated_at: 2026-11-23T19:10:59.200Z
---
In #762's local full suite (PYTEST_WORKERS=3, load average about 280-300), two tests failed and then passed alone: (1) test_project_local_plugin_discovery::test_pytest_collection_ignores_operator_plugin_env, whose subprocess --collect-only hit the test's own 30 s timeout; (2) test_chrome_starts::test_a_start_that_never_writes_a_port_is_not_made_again, which counted starts == 0, probably because the hanging stand-in did not record its start within the launcher's 1.5 s bound (unverified). Both assert a time bound rather than a causal order. Make each wait on the event it means to observe. Related: mb-p9b0. Evidence: .claude/worktrees/fix-mirror-pm/attic/full-python-762a.txt
