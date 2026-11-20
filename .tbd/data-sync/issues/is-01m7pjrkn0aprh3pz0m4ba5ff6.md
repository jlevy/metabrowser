---
type: is
id: is-01m7pjrkn0aprh3pz0m4ba5ff6
title: "Chrome tests: retire the per-test allowances for a cold Chrome start now that the run warms Chrome up"
kind: task
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7wysgm9rg3fdch55nst1wrn
created_at: 2026-11-18T05:41:06.331Z
updated_at: 2026-11-20T17:19:01.046Z
---
From review A on #554 (A11). Many Chrome modules size their session bounds for a cold start inside the test ('A cold Chrome start in CI has taken 28.2 s', e.g. tests/test_changed_file_rows_chrome.py, tests/test_control_chords_chrome.py, tests/test_diff_markdown_fold_chrome.py, and the 'bounds at 30 s' notes in tests/test_folder_home_chrome.py, tests/test_nav_reveal_chrome.py, tests/test_type_scale_chrome.py and others), and tests/test_github_pull_header_chrome.py orders a 'launch' part first with LAUNCH_TIMEOUT_S to absorb the job's first start. With #554's warm-up (tests/chrome_starts.py) taking that start, those reasons stop holding (AGENTS.md: delete a rule whose reason no longer holds). Unblock: #554 merged and a few CI runs' 'chrome starts:' lines show every per-test start warm. Then re-measure each module's session from those runs, tighten its bound and comment, and drop or keep the header test's launch part on the evidence.
