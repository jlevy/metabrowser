---
type: is
id: is-01m8bkxf108ayt40j2hhjkrxm5
title: "Address link destination regressions in Metabrowser PR #874"
kind: bug
status: in_progress
priority: 2
version: 9
spec_path: docs/project/specs/active/plan-2026-11-26-in-app-link-resolution.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8bat4973h1bjzvpkwd8qjdy
child_order_hints:
  - is-01m8bn1kpy7rmt61pa9cpe98vb
  - is-01m8bn1mmdqe29jda7s8wcjd0a
  - is-01m8bn1nm536e9ms4h3xg2se2r
  - is-01m8bn1pxs0k2k2yqgq8wbj4ec
  - is-01m8bn1r9yzzbepm9pgzjc2a52
  - is-01m8bn1s4c8myz0ze4mqzk3yn6
  - is-01m8bn1takqr0769p4v8e6bxat
hold: null
hold_until: null
created_at: 2026-11-26T09:45:17.066Z
updated_at: 2026-11-26T10:05:08.306Z
started_at: 2026-11-26T09:58:28.795Z
---
At head 2bf458b8, a valid absolute GitHub patch link is rewritten as a repository path, headings disappear from Markdown links routed to Changes, and old-only comparison paths are treated as head files. The review of PR #874 also covers missing local commit targets, stalled optional asset loading, and lossless GitPath fallback. Review the findings in https://github.com/jlevy/metabrowser/pull/874 before merging.
