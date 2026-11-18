---
type: is
id: is-01m7p8a6wypg3abhfbqs0e04p6
title: One-run listing spells its own copy of the manifest listing options
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7n6v8n050erzeb13c5tasar
created_at: 2026-11-18T02:38:28.765Z
updated_at: 2026-11-18T02:38:28.765Z
---
Review of #530 (B5). GitDiffSource._patch(listing=True) passes its own literal listing options while MANIFEST_LISTING_OPTIONS (diff/adapters/git.py) is the kept manifest's identity. Only the listing-alone run writes the bank today; if the pull path adopts the one-run listing, derive its options from MANIFEST_LISTING_OPTIONS or assert the two equal.
