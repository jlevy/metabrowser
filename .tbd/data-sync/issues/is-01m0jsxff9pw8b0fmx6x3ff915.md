---
type: is
id: is-01m0jsxff9pw8b0fmx6x3ff915
title: Goldens for /api/git/repo, refs, log, and commit
kind: task
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-cli-parity-and-golden-coverage.md
labels: []
dependencies: []
parent_id: is-01m0jsvvcqw7knvxbaq4sn6ddj
created_at: 2026-08-21T18:39:15.432Z
updated_at: 2026-08-30T00:48:26.697Z
closed_at: 2026-08-30T00:48:26.692Z
close_reason: cli-api-git.tryscript.md pins /api/git/repo, refs, summary, log, and commit against a deterministic fixture repository, asserting real revisions. Added page_cursor to the session schema as an unconditionally-normalized field, found by measuring two runs.
resolution: null
duplicate_of: null
---
The whole Git panel reads from these four routes and none has a CLI equivalent. Needs a fixture repository with pinned revisions and author dates so the transcript is deterministic; revisions normalize through the session schema.
