---
type: is
id: is-01m6g9jsp8gs0esdtpf4g7j2nw
title: "PR #288 B1: validate cache layout before reusing an unattached source"
kind: bug
status: open
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m6g5eqdtdmc5pj1eb9ryy6s1
created_at: 2026-11-03T08:49:30.311Z
updated_at: 2026-11-03T11:44:16.318Z
---
Independent strong review at ef7045b9: publish_unattached_source existing-source fast path bypasses layout/config preflight, allowing PR metadata writes into future f02 layout after checkout fallback swallows cached_source refusal. Network-free probe confirms mutation. Reject before writes and preserve path-free cache_unwritable.

## Notes

2026-11-03 independent-review integration at final tip 58270d69. Review C independently verifies B1 fixed by 77436af4 with strengthened13531d01 fingerprints: future cache formats refuse before mutation, including the existing unattached-source path. Retained at final #288 58270d69. Final full verification, publication and remote CI are coordinator gates still pending; no PR merged.
