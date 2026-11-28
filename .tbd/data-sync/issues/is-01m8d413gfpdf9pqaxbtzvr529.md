---
type: is
id: is-01m8d413gfpdf9pqaxbtzvr529
title: "One readiness vocabulary: each meaning one glyph at two sizes, conflicts orange, check glyphs only for checks"
kind: feature
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-26-pull-request-merge-readiness.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/917
    at: 2026-11-27T10:01:42.909Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/923
    at: 2026-11-27T18:52:17.804Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/924
    at: 2026-11-27T18:52:17.805Z
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m8be438xa5kc27fpbd5rkbcy
hold: null
hold_until: null
created_at: 2026-11-26T23:46:08.014Z
updated_at: 2026-11-28T17:18:27.456Z
started_at: 2026-11-26T23:47:16.874Z
closed_at: 2026-11-28T17:18:27.453Z
close_reason: "Merged status vocabulary, Pulls row layout, and readiness wording in stack #925 (#917, #923, #924) after review and passing CI."
resolution: null
duplicate_of: null
---
Owner asked 2026-11-26. The page's readiness badge is text only and the Pulls column and stack rows draw a separate glyph set, so the two are different codes for the same thing; and every unmet requirement is the same red. Revise to one vocabulary: each verdict and requirement status one glyph, the page chip its glyph plus label, the compact form (Pulls column, stack rows, narrow header) the same glyph alone, the Merge status rows and the Checks tab's per-check icons the same glyphs. Glyphs a family of circles whose inner mark is the mnemonic; the check marks (circled check, x, pending, dashed, exclamation or triangle) only for checks; conflicts their own mark. Tones follow Primer's roles: conflicts severe (orange), failing checks danger (red), waiting attention, ready success; the server's tone follows the requirement kind as well as its status. Show the owner a rendered vocabulary sheet (light and dark, before and after) before merging.
