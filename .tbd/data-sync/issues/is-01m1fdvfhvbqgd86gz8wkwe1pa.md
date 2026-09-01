---
type: is
id: is-01m1fdvfhvbqgd86gz8wkwe1pa
title: Do not annotate installed environments nested under a Git checkout as source builds
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-09-01T21:26:25.595Z
updated_at: 2026-09-01T21:26:25.595Z
---
build_version.source_checkout() assumes any Git worktree above metabrowser.__file__ means an editable source checkout. The documented release loop creates installed virtualenvs under .bench/, so both a PyPI v0.9.0 control and candidate report the enclosing checkout's commit/dirty state despite distinct correct importlib.metadata versions. Detect installed site-packages independently of an enclosing repository, retain annotations for true editable installs, add nested-venv regression coverage, and reconcile the release-loop docs.
