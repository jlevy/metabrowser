---
type: is
id: is-01m2fcz8t86c9g684tt6dkfgg0
title: "PR #118 review R1: file header and diff file bar two-size rows do not share a baseline"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m2fcz83jz15cmfj6yfdvm1sq
created_at: 2026-09-14T07:26:43.014Z
updated_at: 2026-09-14T07:58:39.475Z
closed_at: 2026-09-14T07:58:39.474Z
close_reason: "Fixed in 0f399e54 (https://github.com/jlevy/metabrowser/pull/118): file/folder header and diff file bar text opt in to align-self: baseline (0 px at DPR 1/2, page and text zoom 90/110%); header path fills its content box; doc is a table of covered rows with the commit meta exception tracked as mb-f3mw."
resolution: null
duplicate_of: null
---
PR #118 review R1 (Medium). docs/design-system.md:639-645 states the baseline rule universally, but .file-header (13px path vs 12px size, measured -0.75px) and .diff-file-toggle (13px .diff-file-path vs 12px .diff-file-note, builtin_plugins/diff/styles.css:77-122) still center. Apply the same opt-in in this PR, measure before/after, extend the test, keep the doc accurate.
