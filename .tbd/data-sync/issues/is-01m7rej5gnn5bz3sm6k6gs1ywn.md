---
type: is
id: is-01m7rej5gnn5bz3sm6k6gs1ywn
title: "Public hygiene: hash each part of a hyphenated or underscored token"
kind: task
status: open
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m03tqjzm7j6qkxjeath5qe0d
created_at: 2026-11-18T23:06:09.813Z
updated_at: 2026-11-20T17:27:49.978Z
---
From review A (A2) on jlevy/metabrowser#565: a private name inside a compound token (name-suffix, name_suffix) escaped devtools/public_hygiene.py, because BANNED_TOKEN_HASHES is checked against whole tokens. Also hash each hyphen- or underscore-separated part, with a test.
