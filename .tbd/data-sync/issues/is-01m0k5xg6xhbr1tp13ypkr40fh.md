---
type: is
id: is-01m0k5xg6xhbr1tp13ypkr40fh
title: Attribute CLI start-to-serving and remove the part that scales with the tree
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-21T22:08:59.101Z
updated_at: 2026-08-21T22:49:01.598Z
---
Start to serving measured 771 ms at 9,000 files, 944 ms at 100,000, and 2,748 ms at 998,560. It should not scale with the tree at all: something in the path to binding the port touches it.

Of the fixed part, importing metabrowser.cli measures 113 ms (python -X importtime) and "uv run python -c pass" about 56 ms, which leaves most of the fixed cost unattributed. Attribute it before optimizing it.

tests/test_startup_nonblocking.py already asserts the first synchronous setup step does not stall the event loop, so the gitignore build is covered; the scaling is somewhere else.
