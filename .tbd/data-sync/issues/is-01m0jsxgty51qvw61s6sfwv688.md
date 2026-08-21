---
type: is
id: is-01m0jsxgty51qvw61s6sfwv688
title: Close every gap row and make check_parity reject them
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-21-cli-parity-and-golden-coverage.md
labels: []
dependencies: []
parent_id: is-01m0jsvvcqw7knvxbaq4sn6ddj
created_at: 2026-08-21T18:39:16.829Z
updated_at: 2026-08-21T18:39:16.829Z
---
The ratchet closes: flip each gap row in the parity table to a command and a golden, then remove the gap allowance from devtools/check_parity.py so a new route cannot land without its CLI equivalent. A parity check that permits gap rows forever is a check nobody reads.
