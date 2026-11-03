---
type: is
id: is-01m6g9jsp8gs0esdtpf4g7j2nw
title: "PR #288 B1: validate cache layout before reusing an unattached source"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m6g5eqdtdmc5pj1eb9ryy6s1
created_at: 2026-11-03T08:49:30.311Z
updated_at: 2026-11-03T08:49:30.311Z
---
Independent strong review at ef7045b9: publish_unattached_source existing-source fast path bypasses layout/config preflight, allowing PR metadata writes into future f02 layout after checkout fallback swallows cached_source refusal. Network-free probe confirms mutation. Reject before writes and preserve path-free cache_unwritable.
