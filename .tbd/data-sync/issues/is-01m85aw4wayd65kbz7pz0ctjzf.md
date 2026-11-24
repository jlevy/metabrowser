---
type: is
id: is-01m85aw4wayd65kbz7pz0ctjzf
title: "PR #766 A1: raw HTML on a thread costs what no budget bounds (formatting rebuild)"
kind: bug
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01m8577az40f83ecdxrw97hmth
created_at: 2026-11-23T23:11:50.151Z
updated_at: 2026-11-24T00:48:47.958Z
---
High finding A1 of review A on PR #766 (https://github.com/jlevy/metabrowser/pull/766#pullrequestreview-6030955099). At src/metabrowser/diff/markdown_projection.py:1099-1101, :813-818, :422-431.

## Notes

Thread path fixed in 1398903ac on PR #766: a thread refuses a side with raw HTML that renders, with a no-reason too_large, so the server asks the Markdown child, whose 10 s deadline stops it; measurement beside _Limits; test_raw_html_projects_only_where_a_deadline_stops_it. Left open while the coordinator decides the further ask, capping the child's memory (mb-zrng, KPress kpr-mgc0): the child reached 1,295 MB on 47,988 B before its deadline.
