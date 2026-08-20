---
type: is
id: is-01m0ghvs0kb57fx1ezhxr6tatr
title: "Ref chips: distinguish tags, trunk, and ordinary branches"
kind: feature
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-08-20T21:40:02.194Z
updated_at: 2026-08-20T21:40:02.194Z
---
Every ref chip currently reads the same apart from local/remote color. Give the three classes distinct, defined treatments: trunk refs (main/master and their origin/ forms) marked as the branch everything merges into, ordinary branches as the base form, and tags a different shape — a left-pointing notch, [branch] vs <tag) — since a tag is a different kind of thing, not a differently-colored branch. Define the border/shape system in design-system.md's Branch Chips section rather than ad hoc, and pin it in tests/test_design_vocabulary.py.
