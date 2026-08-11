---
type: is
id: is-01kzsb4k9hwrt25jj9j6svkvaf
title: "Repo cache: URL-aware ROOT and serve wiring, plus --cache and --cache-purge modes"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies: []
created_at: 2026-08-11T21:19:59.280Z
updated_at: 2026-08-11T21:19:59.280Z
---
Detect URL on the raw ROOT string before Path resolution; strip query and fragment; reject /tree/ and /blob/ deep links with a message naming the plain repo URL. Substitute the cached path before run_serve's directory checks and report the originating URL. Background backfill after serving, never fatal. Add --cache and --cache-purge to _MODE_OPTIONS; purge reports before removing and tolerates EACCES on read-only git objects.
