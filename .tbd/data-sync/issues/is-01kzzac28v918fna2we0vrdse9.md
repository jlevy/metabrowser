---
type: is
id: is-01kzzac28v918fna2we0vrdse9
title: "PR #40 review R8: make compatibility packet exports exact and verifiable"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01kzzabe6f9r3fwtbd3w4tddqy
created_at: 2026-08-14T05:02:02.010Z
updated_at: 2026-08-14T05:25:17.936Z
closed_at: 2026-08-14T05:25:17.935Z
close_reason: "Fixed: packet export prunes stale contents and self-verifies; --verify validates safe paths, exact contents, manifest shape, and hashes."
---
PR #40 comment 5289663054, R8. Export must prune stale destination content and provide a verify mode that checks manifest membership and digests after transfer. Add end-to-end tests and docs.
