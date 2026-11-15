---
type: is
id: is-01m7dqrczwe5g7q2c8ja0vbz94
title: "Architecture: repository cache, mirrors, GitHub pull requests"
kind: task
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7dqmdjvjrgqd3vpqw3z3zdc
created_at: 2026-11-14T19:15:12.507Z
updated_at: 2026-11-15T08:17:02.977Z
closed_at: 2026-11-15T08:17:02.975Z
close_reason: Implemented on claude/docs-first-principles (one standalone PR)
resolution: null
duplicate_of: null
---
Phase 2, PR 3: repository cache, mirrors, and GitHub.

- New arch-repository-cache.md (about 250 lines): layout, identity, record contracts, locks, and sweep.
- New arch-mirror-acquisition-and-refresh.md (about 300): transports, credentials, the lending checkout, refresh cadence. The owner of the beside-a-checkout cases.
- New arch-github-pull-requests.md (about 350): records, the catalog, files, checks, stacks, and routes. Copy route contracts from the repository document :624-1238 and arch-views-models-routes.md :178-646 (the map-and-entry PR deletes them there). Fold in the designs of plan-2026-10-01-github-pulls-tab.md and plan-2026-11-02-pr-review-mirror-and-checkout.md.
- Retire arch-repository-sources-and-provider-mirrors.md (1,768 lines), moving the paths devtools/check_artifact_contracts.py:19-21 reads; update its inbound anchors (15 anchors from 24 files) and the comments in src/ that name it (three files).

Known errors to fix:
- Its status (:6-7, :27-28) has two false clauses.
- :1732-1733 says "never retried"; cache/pull_refs.py:95-96 retries.
- :134-137 capability fields differ from source.py:44-57.
- :1381 and :387-392 name types that do not exist.
- :1736-1738 lists the built probe as open.
- About 120 lines are replacement history.
