---
type: is
id: is-01m6ka2s3sdeg2w75kbadkvk7v
title: Describe the current rank-based ToneBand palette policy
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T12:55:57.304Z
updated_at: 2026-11-04T17:21:01.570Z
closed_at: 2026-11-04T17:21:01.570Z
close_reason: "All 17 accepted documentation findings corrected in reviewed/merged PR #298 and independently verified on its exact final-main tree. Completed against actual final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9; final independent integration review and all nine main CI jobs passed. Original evidence retains its execution pins; genuine future and release scope remains separate."
resolution: null
duplicate_of: null
---
Expanded documentation review D4: the current design-system palette prose says families differ only by hue and share one lightness/chroma pair per theme. This contradicts ToneBand.at and registry rank-derived per-family positions, as well as the later explanation in the same guide. Correct the normative paragraph to describe current ToneBand policy with source references; preserve dated experiments and make no product color change. Independently verify the final wording against color_oklch.py and file_type_registry.py.
