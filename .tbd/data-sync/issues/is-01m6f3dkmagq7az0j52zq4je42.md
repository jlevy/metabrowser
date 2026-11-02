---
type: is
id: is-01m6f3dkmagq7az0j52zq4je42
title: "Keyboard: walking changed files jumps the diff to that file"
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6f39zpnk9rc3kjy552b88qj
created_at: 2026-11-02T21:42:34.377Z
updated_at: 2026-11-02T21:42:34.377Z
---
The user, 2026-11-02: easy to scroll through files within a PR, and it may require rapid scrolling of the diff view to the relevant file when we navigate between files. Acceptance: changed-file rows are a Navigational Row Collection with the same contract as PR rows. Moving between files scrolls the diff straight to that file's bar, an immediate jump and not smooth scrolling, and focus stays in the nav. The file arrives hydrated even past MAX_HYDRATED_FILES, since builtin_plugins/diff/sidekick.py has a wanted_file path. Holding a key queues no request per row: latest wins, older ones cancelled. The position holds: neighbours hydrating above the target must not move it, and Back's history.state.pullPlace restore is kept. The selection follows a reader who scrolls the diff by hand, without stealing focus. It holds on the stress case, a real pull request of 1,183 files and +281,131 lines, so the tree stays bounded or virtualized; budgets come from the performance study. Pin in a browserless session with a golden, plus real-Chrome evidence for the scrolling.
