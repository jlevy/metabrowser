---
type: is
id: is-01m8f4vb75dzwj27esrsawy140
title: Compute pull refresh receipt identity only when needed
kind: task
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m8f20t1bj6kw6s6haf15e6k7
created_at: 2026-11-27T18:38:56.737Z
updated_at: 2026-11-27T18:41:22.838Z
closed_at: 2026-11-27T18:41:22.833Z
close_reason: Fixed and independently verified in 8d8d854. Only the PR receipt path computes the memoized record identity.
resolution: null
duplicate_of: null
---
PR #922 performance review identified extra record serialization during large-stack polling. Keep receipt identity lazy and cached on each parsed record.
