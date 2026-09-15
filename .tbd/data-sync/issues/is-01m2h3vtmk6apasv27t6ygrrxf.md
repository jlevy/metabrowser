---
type: is
id: is-01m2h3vtmk6apasv27t6ygrrxf
title: "GitHub Phase 3: bounded PR index and selected hosted-review bundles"
kind: feature
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
dependencies: []
parent_id: is-01m10xd666fefs5z7ft5m58zj0
created_at: 2026-09-14T23:26:01.873Z
updated_at: 2026-09-14T23:50:51.633Z
---
Cache a bounded repository-scoped ChangeRequestIndex and hydrate selected ChangeRequest bundles through the gh adapter. The index stores provider-neutral summaries, query identity, pages/cursors, completeness, freshness, validators, and rate-limit outcomes; direct PR URLs can bypass it and hydrate one bundle. The selected PR is a SoftSchema frontmatter-md artifact whose YAML holds consumed values and whose Markdown body is the description, plus bounded review, thread, check, status, and ref companions. Do not mirror every PR, retain raw API responses, or fetch Git refs for list rows; core fetches only selected base/head/optional merge refs.
