---
type: is
id: is-01kxqgta5yrksvdcnqg7c5hkg4
title: Add a public-safe README screenshot without local filesystem paths
kind: task
status: closed
priority: 2
version: 3
labels: []
dependencies: []
created_at: 2026-07-17T07:49:21.213Z
updated_at: 2026-07-17T17:28:27.484Z
closed_at: 2026-07-17T17:28:27.484Z
close_reason: "Completed in e4df7ac: preserved the owner's README voice, documented runtime and contributor prerequisites, retained the shared Node 24.18/npm 11.10 floor, scoped Markdown spacing fixes to the KPress host, regenerated the neutral-path screenshot after a settled render, added regression coverage, passed make verify with 705 tests, and passed GitHub Actions run 29600115127."
---

## Notes

The current local screenshot contains a personal absolute filesystem path and was deliberately excluded from the public commit. Retake it against a neutral demo directory or redact the path before adding it to the README.
