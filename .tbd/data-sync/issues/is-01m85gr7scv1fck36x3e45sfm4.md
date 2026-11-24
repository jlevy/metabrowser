---
type: is
id: is-01m85gr7scv1fck36x3e45sfm4
title: Agent sessions inherit PYTHONDONTWRITEBYTECODE=1, so every test process and metab start compiles its modules from source, doubling import CPU
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-24T00:54:33.514Z
updated_at: 2026-11-24T00:54:33.514Z
---
The Claude Code process environment sets PYTHONDONTWRITEBYTECODE=1. It is not in the user's shell files. Every Python process an agent session starts therefore never writes .pyc files. A worktree that has never been imported outside a session has none, so every import compiles from source. pytest's assertion rewriter honours the same flag and never caches its rewritten modules; with python_files = ['*.py'] (pyproject.toml:249) that covers every module under tests/. Measured 2026-11-23 in a fresh worktree at a load average near 315: 'import metabrowser.server, metabrowser.cli.main' took 1.06-1.20 s of user CPU as the session runs it, and 0.53 s with the variable unset and a warm PYTHONPYCACHEPREFIX cache. Earlier the same day a one-test pytest process took 3.6-4.0 s of CPU against 1.2-1.45 s with a warm cache. At load 400 or more on 10 cores, contention multiplies this to tens of seconds of wall time per process. It inflated the startup of the stand-in server (mb-9lyt) and of each recorder measured for mb-gguk and mb-skzz, so local timings from agent sessions overstate what a developer's terminal or CI sees (CI writes bytecode). Options, not chosen here: unset it in the Makefile's test targets, or set PYTHONPYCACHEPREFIX to a gitignored directory so that bytecode is written without touching the tree.
