---
type: is
id: is-01m87bz07evg105pftfep1e0sg
title: "PR #771 A5: the kpress==0.3.10 supply-chain row lacks the SHA-256 match"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m87bxfh1ymbm8c10h6rzs8gx
hold: null
hold_until: null
created_at: 2026-11-24T18:09:21.122Z
updated_at: 2026-11-24T18:30:19.050Z
started_at: 2026-11-24T18:15:56.808Z
closed_at: 2026-11-24T18:30:19.046Z
close_reason: "Fixed in 61f1f1083: the kpress==0.3.10 row records wheel 205d7f58…f9a28ab1 and sdist 8a00b909…cd5c110e matching uv.lock; full digests checked against PyPI's JSON API (not yanked)."
resolution: null
duplicate_of: null
---
Low. SUPPLY-CHAIN-SECURITY.md:46-49 and :56. Record the wheel and sdist SHA-256 match against uv.lock. PR #771, review https://github.com/jlevy/metabrowser/pull/771#pullrequestreview-6044731578
