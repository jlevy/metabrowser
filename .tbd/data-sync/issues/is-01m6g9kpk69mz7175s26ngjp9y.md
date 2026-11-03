---
type: is
id: is-01m6g9kpk69mz7175s26ngjp9y
title: "PR #288 B2: attach companions adopted during store upgrade"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m6g5eqdtdmc5pj1eb9ryy6s1
created_at: 2026-11-03T08:49:59.909Z
updated_at: 2026-11-03T08:49:59.909Z
---
Independent strong review: companion threaded read can start with ListedRepository, store attaches while it awaits, then newly adopted companion remains metadata-only forever although group git_dir is attached. Rebind/version-check current published source before _keep; deterministic different-PR barrier test.
