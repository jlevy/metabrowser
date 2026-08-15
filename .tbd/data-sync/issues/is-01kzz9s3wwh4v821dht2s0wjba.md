---
type: is
id: is-01kzz9s3wwh4v821dht2s0wjba
title: Remove icons from file-type overview group headings
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
created_at: 2026-08-14T04:51:41.083Z
updated_at: 2026-08-14T04:57:46.497Z
closed_at: 2026-08-14T04:57:46.496Z
close_reason: Implemented text-only aggregate headings, renamed the UI fallback to Other types, added regression coverage, and passed make verify plus PR CI.
---
In the folder Files overview, No extension and Other types are grouping headings and must not render file icons. Rename Remaining types to Other types. Preserve icons for individual extension rows only, and add focused regression coverage.
