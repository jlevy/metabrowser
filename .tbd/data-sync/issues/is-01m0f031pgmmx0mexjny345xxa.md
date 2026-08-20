---
type: is
id: is-01m0f031pgmmx0mexjny345xxa
title: "PR #58 review R8: Schema/impl drift: algorithm enum unenforced; explicit-null handling differs Python vs JS"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0f02zaw865q3swdc9xvmdb9
created_at: 2026-08-20T07:10:11.663Z
updated_at: 2026-08-20T07:35:57.521Z
closed_at: 2026-08-20T07:35:57.520Z
close_reason: "R8 fixed in c0ae341: null-as-absent aligned across schema/Pydantic/JS, DiffAlgorithm StrEnum + JS set, corpus cases explicit-nulls-are-absent and bad-algorithm"
---
PR #58, review 4979975854, finding R8. Schema/impl drift: algorithm enum unenforced; explicit-null handling differs Python vs JS. Align null policy, StrEnum algorithm, corpus cases. format.py:224, diff_model.js:246, schema:84
