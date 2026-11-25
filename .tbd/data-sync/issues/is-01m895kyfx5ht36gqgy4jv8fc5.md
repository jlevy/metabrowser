---
type: is
id: is-01m895kyfx5ht36gqgy4jv8fc5
title: "PR CI's --skip-slow Chrome tier let #835 merge with test_files_totals_stable_chrome unrun; main's push run caught it"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-11-25T10:56:56.316Z
updated_at: 2026-11-25T10:56:56.316Z
---
While main is green, devtools/ci_plan.sh picks test-chrome-fast with --skip-slow (drops tests >=20 s). test_files_totals_stable_chrome (~120 s) never ran on #835's PR run 45595908031, so #835 merged and turned main red (run 45596649361); fixed by #839 (mb-1t9k). Decide how a PR's Chrome tier covers slow tests that its changed files affect (e.g. select slow tests by touched modules, or run the full Chrome tier when static/ shell scripts change).
