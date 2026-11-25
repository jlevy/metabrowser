---
type: is
id: is-01m0dkj0xzgg9b6kc7ge0fm2ne
title: "Archive containers: browse .zip through the container contract"
kind: feature
status: closed
priority: 3
version: 5
spec_path: docs/project/architecture/arch-nav-containers.md
delegate: null
labels: []
dependencies: []
parent_id: is-01kxj6mrvpkqnkn274rhy3mg2j
hold: null
hold_until: null
created_at: 2026-08-19T18:11:56.478Z
updated_at: 2026-11-25T01:32:17.089Z
started_at: 2026-09-16T21:12:28.653Z
closed_at: 2026-11-25T01:32:17.053Z
close_reason: Superseded by the archive plan (docs/project/specs/active/plan-2026-11-24-archive-contents-and-browsing.md). Archives have directories, so members cannot be flat item-like rows as this sketch assumed; Phase 2 adds folder-like container children (mb-0dja) and member sources (mb-xyz9) instead.
resolution: null
duplicate_of: null
---
The generality proof for nav containers: a .zip is folder-like (children = members via bounded listing, outer = archive summary/listing view), members are ordinary item-like entries whose kinds are detected as usual, and extraction goes through the shared container materialization cache. No new tree or rendering machinery — if this needs any, the container contract is wrong. Bounded: listing caps, per-member size caps, zip-bomb guards per SUPPLY-CHAIN thinking.
