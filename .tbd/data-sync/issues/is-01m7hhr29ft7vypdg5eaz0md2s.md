---
type: is
id: is-01m7hhr29ft7vypdg5eaz0md2s
title: "Release 0.13 owner: make the Developer ID identity valid (install Apple's Developer ID G2 intermediate; confirm find-identity -v shows 1) and store the notarytool profile metabrowser-notary"
kind: task
status: open
priority: 1
version: 3
labels: []
dependencies:
  - type: blocks
    target: is-01m7hhr43k5rc7ytbxg1vx031s
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
created_at: 2026-11-16T06:47:07.822Z
updated_at: 2026-11-21T20:58:07.879Z
---

## Notes

2026-11-17: per the merged publishing plan (#485, O1-O9), the owner steps are: install the Developer ID G2 intermediate; create an App Store Connect team API key; set up a dedicated release keychain and import the identity with -x, keeping the offline .p12; store the metabrowser-notary profile; turn on immutable releases.
