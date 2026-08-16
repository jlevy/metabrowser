---
type: is
id: is-01kzs5m38dz1egphfwf30c8h7n
title: "Open a Git URL directly: purgeable repo cache with blobless clone + background backfill"
kind: feature
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies: []
created_at: 2026-08-11T19:43:35.692Z
updated_at: 2026-08-16T08:05:43.412Z
extensions:
  linear:
    id: 06ad4ed9-e57c-43ff-a0bd-72bc542de8f5
    linked_at: 2026-08-16T08:05:43.412Z
---
Accept a Git URL as ROOT: clone into a purgeable cache (~/.metabrowser/cache/repos/<host>/<owner>/<repo>) with --filter=blob:none, serve as soon as the checkout exists, and run git backfill in the background so history browsing works without a first-blame stall. Research: docs/project/research/research-2026-08-11-repo-cache-and-git-url-open.md. Gated on mb-vib1 (untrusted-content profile) since a fetched repo is third-party content. Includes cache layout, purge command, Git preflight, and a skill routing line.
