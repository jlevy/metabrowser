---
type: is
id: is-01m78v9q6ww211gywhwc0yk159
title: Every failure the UI or CLI shows names the command that fixes it
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-11-12T21:40:53.595Z
updated_at: 2026-11-12T21:40:53.595Z
---
The user, 2026-11-12: 'even in cases like this where something is wrong, it should list the command to run to do the desired thing.' The cache_unwritable message says to 'clear the affected repository cache and retry' without naming the repository, its cache path, or the command. Give this message, and the other remediation messages in the same family, the exact runnable command (a metab command if one exists, adding one through a route with its parity row and golden if needed, per AGENTS.md's CLI parity rules), and the affected repository.
