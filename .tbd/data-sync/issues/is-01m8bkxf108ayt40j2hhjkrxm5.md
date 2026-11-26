---
type: is
id: is-01m8bkxf108ayt40j2hhjkrxm5
title: "Address link destination regressions in Metabrowser PR #874"
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-26-in-app-link-resolution.md
labels: []
dependencies: []
parent_id: is-01m8bat4973h1bjzvpkwd8qjdy
created_at: 2026-11-26T09:45:17.066Z
updated_at: 2026-11-26T09:45:17.066Z
---
At head 2bf458b8, a valid absolute GitHub patch link is rewritten as a repository path, headings disappear from Markdown links routed to Changes, and old-only comparison paths are treated as head files. The review of PR #874 also covers missing local commit targets, stalled optional asset loading, and lossless GitPath fallback. Review the findings in https://github.com/jlevy/metabrowser/pull/874 before merging.
