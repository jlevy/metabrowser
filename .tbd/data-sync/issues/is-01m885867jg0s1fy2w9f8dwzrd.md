---
type: is
id: is-01m885867jg0s1fy2w9f8dwzrd
title: "Archive phase 1: classifier changes, reader, listing route, and kind"
kind: task
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-24-archive-contents-and-browsing.md
labels: []
dependencies:
  - type: blocks
    target: is-01m885941n5xs6ap60sm1avesc
  - type: blocks
    target: is-01m885969bezeyfe7tcepdtszx
parent_id: is-01kxj6mrvpkqnkn274rhy3mg2j
created_at: 2026-11-25T01:31:16.593Z
updated_at: 2026-11-25T01:53:49.347Z
---
Phase 1 layer 1 of the archive plan (Implementation Plan, Phase 1). Four generic classifier changes: compound extensions in ext/exts, binary rules at every pin site, name-based compound binary rules before the gzip sniff (a claimed .tar.gz keeps its stored bytes; Decision 10), and restrict_exts on magic rules. The archive plugin's manifest and kinds; names.py (every Safety Rules row, including overlapping, bad_name, g1- escaping, surrogate escaping before JSON); reader.py with its own ZIP central-directory and tar header parsers (no zipfile/tarfile extraction); index cache; the store with STORE_MAX_* bounds and streamed pin copies; the listing hook. Fixtures, edge tests, measurements. Same layer: cli-api-archive-listing golden, cli-show kind lines on folder and pin, the route's parity row, the views map row, and the built-in plugin lists.
