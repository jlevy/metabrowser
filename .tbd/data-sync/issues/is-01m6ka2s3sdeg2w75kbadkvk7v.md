---
type: is
id: is-01m6ka2s3sdeg2w75kbadkvk7v
title: Describe the current rank-based ToneBand palette policy
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T12:55:57.304Z
updated_at: 2026-11-04T12:55:57.304Z
---
Expanded documentation review D4: the current design-system palette prose says families differ only by hue and share one lightness/chroma pair per theme. This contradicts ToneBand.at and registry rank-derived per-family positions, as well as the later explanation in the same guide. Correct the normative paragraph to describe current ToneBand policy with source references; preserve dated experiments and make no product color change. Independently verify the final wording against color_oklch.py and file_type_registry.py.
