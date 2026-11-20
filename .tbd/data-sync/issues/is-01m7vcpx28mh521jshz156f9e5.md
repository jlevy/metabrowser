---
type: is
id: is-01m7vcpx28mh521jshz156f9e5
title: Wiki image embed stays at 'Resolving link (catalog-incomplete)' in a live metab
kind: bug
status: open
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7wysdnvzch4gb5zvqwvn04e
created_at: 2026-11-20T02:31:31.143Z
updated_at: 2026-11-20T17:13:50.021Z
---
Seen while verifying PR 626 (mb-5xq7): in a live metab, a real ![[icon.png|100x50]] never resolved; it sat at 'Resolving link (catalog-incomplete)' for 30 s, both inside a gitignored attic/ and in a root outside git. Under --untrusted it renders as text (expected). Unconfirmed whether a real bug or a gap in the probe; reproduce first with a small root holding icon.png and a README.md embedding it.
