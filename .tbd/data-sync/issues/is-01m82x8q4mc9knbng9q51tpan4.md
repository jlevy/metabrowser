---
type: is
id: is-01m82x8q4mc9knbng9q51tpan4
title: Show GitHub pull requests automatically for local checkouts opened from File
kind: bug
status: open
priority: 0
version: 1
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
created_at: 2026-11-23T00:35:33.136Z
updated_at: 2026-11-23T00:35:33.136Z
---
The Mac File menu opens an existing local Git checkout and recognizes it as Git, yet the PR catalog is absent. Diagnose the actual Mac open path and GitHub remote/auth detection, preserve local checkout behavior, and make eligible local GitHub repositories expose and load their PR catalog automatically. Verify with a controlled remote fixture and the affected local checkout without sharing private repo data.
