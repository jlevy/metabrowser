---
type: is
id: is-01kzy6th25xazbwyf8xqmn5j89
title: Apply shared size emphasis in folder Overview
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - ui
  - overview
dependencies: []
parent_id: is-01kzwg302q9172bvjc543whcte
created_at: 2026-08-13T18:40:47.172Z
updated_at: 2026-08-13T18:50:42.579Z
closed_at: 2026-08-13T18:50:42.578Z
close_reason: Overview file counts and byte sizes now use the navigation panel's shared magnitude thresholds across breakdown, Total, and Ignored rows; tests, docs, live browser inspection, and make verify pass.
---
Folder Overview metric values do not consistently use the navigation panel's shared size and file-count emphasis thresholds: byte values receive only the neutral size class, file counts receive neither count class, and Total values are forced bold independently of their magnitude. Route every File types row, including Total and Ignored, through shared count/count-large and size/size-large class helpers, keep labels semantically emphasized, document the cross-surface rule, and cover live updates plus threshold boundaries.
