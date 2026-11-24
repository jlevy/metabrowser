---
type: is
id: is-01m854naembn4kppaqf2ztnqjm
title: check_parity silently skips a registry row with an escaped pipe
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-09-10-functional-ui-cli-parity.md
labels: []
dependencies: []
parent_id: is-01m26hjjvhpcf49p2x1c3390kk
created_at: 2026-11-23T21:23:15.027Z
updated_at: 2026-11-23T21:23:15.027Z
---
devtools/check_parity.py functional_parity_rows splits table rows on '|' and drops any row without exactly 6 cells, so a row containing an escaped pipe is ignored while the check reports passed (found in PR #765: the count moved 303 to 304 only once the pipes were removed). Parse escaped pipes, and fail on a row it cannot read.
