---
type: is
id: is-01m0vscy963c6aphv6ga8wmxww
title: Implement a bounded virtual window for Git history rows
kind: task
status: open
priority: 1
version: 2
labels:
  - release:v0.8.0
dependencies:
  - type: blocks
    target: is-01m0vsd8dnak6hw2b87x5awch6
parent_id: is-01m0ghvrnps0hh3m8d28xvfn2j
created_at: 2026-08-25T06:23:23.429Z
updated_at: 2026-08-25T06:23:33.811Z
---
Render only a measured window around the viewport while preserving scroll geometry with spacers. Keep row identity, graph lane continuity, ref colors, focus, selection, hover detail, and commit routes correct when rows mount, unmount, and remount. Give all observers and listeners disposal paths. Test bounded mounted-row counts, window transitions, focus recovery, and replacement without depending on timing.
