---
type: is
id: is-01m8e7927wvgqsb5mz3wfzq15z
title: Main Chrome stack-groups fixture assigns shared PR to a different stack
kind: bug
status: closed
priority: 1
version: 4
delegate: codex@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-27T10:02:08.995Z
updated_at: 2026-11-27T10:07:40.562Z
started_at: 2026-11-27T10:03:31.986Z
closed_at: 2026-11-27T10:07:40.561Z
close_reason: Exact alternate-membership symptom already tracked in mb-v719; diagnosed fixture startup mismatch and supplied reviewed green repair 66f5942092fd932303efe54d96d04986eb6ebcdc for parent integration.
resolution: duplicate
duplicate_of: is-01m7kpndww8wehzg3zya4x6wy5
---
Main run 45976882655 at 63a00c89e failed the stack-group Chrome membership checks: shared PR 10 sat under Stack 300 while the test expected Stack 286. The alternate-membership symptom is already tracked in the 2026-11-26 notes of mb-v719, which qualifies it for one main-CI rerun. The fixture boosted closed PR 8 while startup scans Open first; the initial stack snapshot therefore ranked Stack 300 through boosted open PR 5. Later closed activity moved the live heading but intentionally did not change snapshot ownership. Fix: boost open member 7 instead, so the first Open scan has the intended ownership.

## Notes

Repair committed as 66f5942092fd932303efe54d96d04986eb6ebcdc on agent/main-chrome-stack-order, based on exact main 63a00c89ec9000c06ceb4377c7a31d7a43619fb7. One test file changed, no production logic. Independently reproduced the same CI assertion cluster locally on unmodified main: uv run --frozen pytest -s --tb=short -ra tests/test_github_pulls_stacks_chrome.py::test_the_pulls_stack_groups_share_the_stack_menus_design_in_chrome => 1 failed in 64.36s, no timeout. After changing the activity boost from closed member 8 to open member 7, exact same command => 1 passed in 25.77s. Existing node tests/dom/github-pulls-stack-groups-session.js recency passed, including unchanged snapshot ownership and tie contracts. Focused Ruff check/format, diff whitespace, codespell and actual pre-commit hooks passed. Isolated worktree clean. No CI rerun, push, PR, or merge performed; parent owns integration/publication.
