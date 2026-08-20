---
type: is
id: is-01m0dkhzdjp1dy3q7kpkz91eb6
title: "Nav containers: item-like and folder-like roles for any tree entry"
kind: feature
status: open
priority: 1
version: 5
labels: []
dependencies:
  - type: blocks
    target: is-01m0dkhzy1f8t3m13d246ezp7x
  - type: blocks
    target: is-01m0dkj0xzgg9b6kc7ge0fm2ne
  - type: blocks
    target: is-01m0dkj19x30mgh6c7y4csg17m
  - type: blocks
    target: is-01m0eb0wvz59swjfh0gbkvjx3t
created_at: 2026-08-19T18:11:54.927Z
updated_at: 2026-08-20T01:02:25.442Z
---
The core contract from docs/project/architecture/arch-nav-containers.md: every tree entry may declare item-like (opens views) and/or folder-like (expands to children; selecting the entry itself opens an overview). Directories are the working precedent — promote their behavior (outer-click overview, disclosure, lazy children, roving focus, selection-follows-focus) into a capability a kind's plugin can declare via a children data hook plus an overview view, and make the tree ask 'does this expand' instead of 'is this a directory'. URL grammar: /view/<container-path>/<inner-path> — container membership is path-shaped. First adopter: the patch/diff container (children = file changes, outer = change-set summary, inner = that file's diff tabs), which subsumes the tree half of mb-p2mi.
