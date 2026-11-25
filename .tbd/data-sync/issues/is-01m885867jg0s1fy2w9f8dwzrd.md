---
type: is
id: is-01m885867jg0s1fy2w9f8dwzrd
title: "Archive phase 1: reader, safety rules, and listing route"
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-24-archive-contents-and-browsing.md
labels: []
dependencies:
  - type: blocks
    target: is-01m885941n5xs6ap60sm1avesc
  - type: blocks
    target: is-01m885969bezeyfe7tcepdtszx
parent_id: is-01kxj6mrvpkqnkn274rhy3mg2j
created_at: 2026-11-25T01:31:16.593Z
updated_at: 2026-11-25T01:31:49.418Z
---
Phase 1 layer 1 of the archive plan (Implementation Plan, Phase 1). Compound extensions in kind rules (an ext entry with an inner dot matches fs_paths.derive_ext, folder and pin alike); the archive plugin's manifest and kind rules (ZIP and ustar magic, compressed tar and pre-POSIX tar by name); names.py with every row of Member Names and Safety Rules; reader.py (bounded file object, ZIP EOCD pre-check, tar and compressed-tar scans); index cache; the pin copy in a first cut of the store; the listing hook. Deterministic and hostile fixtures, unit tests at every bound's edge, measurements that set the Phase 1 constants (recorded beside each), cli-api-archive-listing.tryscript.md, and kind: archive lines in cli-show.tryscript.md on a folder and a pin.
