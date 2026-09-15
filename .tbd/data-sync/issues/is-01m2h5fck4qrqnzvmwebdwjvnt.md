---
type: is
id: is-01m2h5fck4qrqnzvmwebdwjvnt
title: Hand-verify v0.10.0 in a real browser before tagging
kind: task
status: open
priority: 1
version: 2
labels: []
dependencies:
  - type: blocks
    target: is-01m2fafd1v8d5pakt6r7zxw5n8
created_at: 2026-09-14T23:54:11.428Z
updated_at: 2026-09-14T23:54:29.218Z
---
Before tagging v0.10.0, check by hand in a real browser on the release candidate: J and K in the file tree (Files and Recent) and in the Git history; the preview's loading spinner, and 'Metabrowser is not reachable' followed by automatic recovery when the server stops and restarts; a Markdown task-list note with [[wiki]] links and ![[embeds]]; tree and Git rows aligned on a shared text baseline; and metab --version for a wheel installed in a .venv inside a git repository, which must print no dev-build annotation (mb-7nij). Record the evidence in exp-034 or the release-prep PR.
