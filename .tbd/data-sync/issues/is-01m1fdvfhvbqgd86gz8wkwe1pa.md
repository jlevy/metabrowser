---
type: is
id: is-01m1fdvfhvbqgd86gz8wkwe1pa
title: Do not annotate installed environments nested under a Git checkout as source builds
kind: bug
status: closed
priority: 1
version: 4
labels: []
dependencies:
  - type: blocks
    target: is-01m2fafd1v8d5pakt6r7zxw5n8
created_at: 2026-09-01T21:26:25.595Z
updated_at: 2026-09-14T07:01:38.057Z
closed_at: 2026-09-14T07:01:38.056Z
close_reason: "Fixed in https://github.com/jlevy/metabrowser/pull/117: source_checkout() annotates only when git tracks the running module file, so wheels in venvs nested under a Git work tree report their installed version; nested-venv regression tests added; CI green."
resolution: null
duplicate_of: null
---
build_version.source_checkout() assumes any Git worktree above metabrowser.__file__ means an editable source checkout. The documented release loop creates installed virtualenvs under .bench/, so both a PyPI v0.9.0 control and candidate report the enclosing checkout's commit/dirty state despite distinct correct importlib.metadata versions. Detect installed site-packages independently of an enclosing repository, retain annotations for true editable installs, add nested-venv regression coverage, and reconcile the release-loop docs.
