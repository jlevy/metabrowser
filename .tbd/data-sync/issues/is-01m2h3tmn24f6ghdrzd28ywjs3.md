---
type: is
id: is-01m2h3tmn24f6ghdrzd28ywjs3
title: Wiki resolver suffix-query keys can exceed the content-hash bound
kind: task
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m2eb9qv8c4rf52j15pcm2j86
created_at: 2026-09-14T23:25:22.978Z
updated_at: 2026-11-14T18:44:26.292Z
---
PR #124 review R2 (Low, deferred): suffixSummaries and suffixQueries key on normalized lookup paths, bounded by MAX_NORMALIZED_TARGET_LENGTH (49,155) rather than by the 16,383-code-unit content-hash bound. Unlike the membership memo the cost is linear rather than quadratic, no mainstream filesystem admits a path component that long, and lowering the semantic bound would make long identities unfindable rather than slow. Revisit if a lookup-heavy profile ever shows it.
