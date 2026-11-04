---
type: is
id: is-01m1nfkxcjwap6bxegmkggh0aw
title: Guard against test fixtures inheriting GIT_DIR into git init
kind: task
status: closed
priority: 2
version: 4
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-09-04T05:52:41.355Z
updated_at: 2026-11-04T17:14:29.955Z
started_at: 2026-11-01T16:05:47.343Z
closed_at: 2026-11-04T17:14:29.955Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Three fixtures ran 'git init' with the ambient environment inherited, so under the pre-push hook — where git exports GIT_DIR and GIT_WORK_TREE pointing at the real repository, taking precedence over cwd — the fixture repo was built in the wrong place. Observed destructively: a linked worktree came back with every tracked file reading as untracked and two commits titled 'first commit' and 'second commit' on its branch.

Fixed in tests/test_cli_show_mode.py (git_root), tests/golden/cli-api-git.tryscript.md and tests/golden/cli-api-plugins.tryscript.md. tests/golden/cli-diff.tryscript.md already unset them, so this had been found once and fixed only where it bit.

metabrowser.git.process._REPO_PINNING_GIT_VARS is the canonical list and its comment describes exactly this failure; production spawns already scrub it.

AGENTS.md says to prefer a check to a sentence. A test that walks tests/ for fixtures invoking 'git init' and asserts each scrubs the pinning variables would make this structural rather than remembered. Only reproducible from a linked worktree under the hook, which is why it survived.

## Notes

2026-11-01: fixed in PR #274, open, CI green at its last read. Close when it merges; its required review has not run.
