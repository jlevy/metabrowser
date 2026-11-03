---
type: is
id: is-01m6fggk2xggcwc9rmdrgcc8v5
title: "PR #284 Qodo 6: debug log records can land on the in-place pull-read status line"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:23.612Z
updated_at: 2026-11-03T02:31:11.553Z
closed_at: 2026-11-03T02:31:11.552Z
close_reason: "Qodo 6 fixed at faab2f01d9b60fb1da14b1e04ba42e0654478419 in e2229f7d: saying_while_waiting runs under maybe_cli_logging(report.end_status_line); test_a_log_record_during_the_wait_gets_a_line_of_its_own."
resolution: null
duplicate_of: null
---
Low (Qodo). https://github.com/jlevy/metabrowser/pull/284#discussion_r4449451263. cli/git_pin_cli.py:209-215, cli/clone_report.py:391-397.
