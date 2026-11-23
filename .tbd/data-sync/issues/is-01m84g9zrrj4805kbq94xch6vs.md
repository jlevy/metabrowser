---
type: is
id: is-01m84g9zrrj4805kbq94xch6vs
title: "Guided PR: show a cited file's whole diff, folded, with the diff's hunk and fold bars"
kind: feature
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7x3g8rdhbeh7f0j0j7nz4sq
hold: null
hold_until: null
created_at: 2026-11-23T15:27:32.094Z
updated_at: 2026-11-23T15:27:46.827Z
started_at: 2026-11-23T15:27:46.825Z
---
A reference with a path and no range shows only its file bar and Open full diff (state file): steps 7-9 of PR 677's guide show no diff at all. Show the file's whole diff in place, drawn by the diff plugin's own file renderer (createFileState/renderFileBody), so it has the diff's blue hunk-header bars and its fold bars that expand long runs, and its syntax tokens. Draw ranged excerpts with the same renderer, as one hunk, so both read alike. The diff plugin offers the renderer as a declared-dependency export (docs/plugins.md, Declared Dependencies); the GitHub plugin requires diff. Bound the payload by the diff source's own per-file patch bounds and MAX_REFERENCES (the measured first paint of Changes).
