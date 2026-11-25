---
type: is
id: is-01m89xmmxah7a0qxwkf9p4dc95
title: "Local Chrome failures under heavy load: guided-review reference rows and Chrome process group kill"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-25T17:56:45.097Z
updated_at: 2026-11-25T17:56:45.097Z
---
While building #842 at load ~200-224: tests/test_github_guided_review_chrome.py::test_guided_review_reference_rows_in_chrome failed once (output lost), and tests/test_process_group.py::test_chrome_keeps_its_processes_in_the_launched_group failed twice (the killed Chrome process group still ran after SIGKILL). Both passed on rerun and on CI. Find the mechanism (likely timing under load); do not rerun away.
