---
type: is
id: is-01m78v9q6ww211gywhwc0yk159
title: Every failure the UI or CLI shows names the command that fixes it
kind: task
status: closed
priority: 1
version: 5
labels: []
dependencies: []
created_at: 2026-11-12T21:40:53.595Z
updated_at: 2026-11-13T06:58:44.558Z
closed_at: 2026-11-13T06:58:44.557Z
close_reason: "Merged in jlevy/metabrowser#386: the cache-clear route, metab --data -, and messages that name the repository and the paste-ready command, kept whole under truncation."
resolution: null
duplicate_of: null
---
The user, 2026-11-12: 'even in cases like this where something is wrong, it should list the command to run to do the desired thing.' The cache_unwritable message says to 'clear the affected repository cache and retry' without naming the repository, its cache path, or the command. Give this message, and the other remediation messages in the same family, the exact runnable command (a metab command if one exists, adding one through a route with its parity row and golden if needed, per AGENTS.md's CLI parity rules), and the affected repository.

## Notes

2026-11-12: jlevy/metabrowser#386 adds POST /api/plugin/github/cache-clear and metab --data -, and gives the pull list, a pull's record, its files, previews, and stack metadata messages that name the repository and the paste-ready command (echo '{}' | metab . --api /api/plugin/github/cache-clear --data -).

2026-11-12: #386 reviewed through A (senior), B (security), C, D, and E; E approves with no findings at 83bb74fb. CI running there. Close once green.
