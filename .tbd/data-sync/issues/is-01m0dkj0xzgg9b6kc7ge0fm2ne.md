---
type: is
id: is-01m0dkj0xzgg9b6kc7ge0fm2ne
title: "Archive containers: browse .zip through the container contract"
kind: feature
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-08-19T18:11:56.478Z
updated_at: 2026-08-19T18:11:56.478Z
---
The generality proof for nav containers: a .zip is folder-like (children = members via bounded listing, outer = archive summary/listing view), members are ordinary item-like entries whose kinds are detected as usual, and extraction goes through the shared container materialization cache. No new tree or rendering machinery — if this needs any, the container contract is wrong. Bounded: listing caps, per-member size caps, zip-bomb guards per SUPPLY-CHAIN thinking.
