---
type: is
id: is-01kxs1n0scnqftrbcsm921bchk
title: Remove elkjs from the base build (no core consumer; 1.59MB of vendored weight)
kind: task
status: closed
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-07-17T22:02:47.980Z
updated_at: 2026-07-17T22:06:14.895Z
closed_at: 2026-07-17T22:06:14.894Z
close_reason: elkjs removed from package.json, vendor manifest, loader, and checks; vendored total 433KB; wheel 454KB; verify green 720 tests.
---
elkjs is referenced only by the index loader list in server.py and the vendored-asset tests — no core JS calls ELK. Drop it from package.json, the vendor manifest, the loader, and the distribution/test expectations; downstream plugins that need graph layout ship it via extra_scripts. Cuts the wheel roughly 920KB -> ~350KB.
