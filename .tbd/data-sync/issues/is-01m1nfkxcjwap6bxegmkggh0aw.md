---
type: is
id: is-01m1nfkxcjwap6bxegmkggh0aw
title: Guard against test fixtures inheriting GIT_DIR into git init
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-09-04T05:52:41.355Z
updated_at: 2026-09-04T05:52:41.355Z
---
Three fixtures ran 'git init' with the ambient environment inherited, so under the pre-push hook — where git exports GIT_DIR and GIT_WORK_TREE pointing at the real repository, taking precedence over cwd — the fixture repo was built in the wrong place. Observed destructively: a linked worktree came back with every tracked file reading as untracked and two commits titled 'first commit' and 'second commit' on its branch.

Fixed in tests/test_cli_show_mode.py (git_root), tests/golden/cli-api-git.tryscript.md and tests/golden/cli-api-plugins.tryscript.md. tests/golden/cli-diff.tryscript.md already unset them, so this had been found once and fixed only where it bit.

metabrowser.git.process._REPO_PINNING_GIT_VARS is the canonical list and its comment describes exactly this failure; production spawns already scrub it.

AGENTS.md says to prefer a check to a sentence. A test that walks tests/ for fixtures invoking 'git init' and asserts each scrubs the pinning variables would make this structural rather than remembered. Only reproducible from a linked worktree under the hook, which is why it survived.
