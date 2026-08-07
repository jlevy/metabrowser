---
type: is
id: is-01kzctf0nb67y8r4b2mjrr1hd6
title: "Research pass 2: broaden file roll-up survey to 12 tools (ncdu, dut, bfs, duc, fsearch, gdu, dua, scc, tokei)"
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-07T00:37:41.663Z
updated_at: 2026-08-07T00:37:46.806Z
closed_at: 2026-08-07T00:37:46.806Z
close_reason: Research doc updated with broader survey, 47-technique catalogue, licensing constraints, and revised design; pending user review
---
Second research pass on the file roll-up engine design: checked out ncdu 1.x/2.x, dut, duc, bfs, fd, scc, tokei, fsearch, gdu, dua-cli, erdtree into attic and read source directly. Findings changed the design: dust is not the perf bar (dut is ~2.8x faster warm); dut's atomic child-refcount gives barrier-free parallel rollups; ncdu 2's seekable block-compressed binary export beats a bulk-read snapshot for lazy navigation; fingerprints should include ctime+inode not just mtime; gdu's SQLite backend proves relational stores are 10-17x too slow. Also catalogued 47 proven techniques with attribution and flagged GPL/LGPL constraints on dut/fsearch/duc.
