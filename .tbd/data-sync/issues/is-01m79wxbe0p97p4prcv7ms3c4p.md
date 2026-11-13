---
type: is
id: is-01m79wxbe0p97p4prcv7ms3c4p
title: Re-measure the 220 KB eager-script validation on a quiet host for the careful 1.1x
kind: task
status: open
priority: 3
version: 2
labels: []
dependencies: []
created_at: 2026-11-13T07:28:19.903Z
updated_at: 2026-11-13T07:46:12.729Z
---
startup_script_transfer_kb = 220 rests on rough-cut evidence (exp-084): every series ran at load average 32-109 on a 10-core host, one series per path, no A/A control; ratio intervals reach 1.14x loopback and 1.11x on the 10 ms link. To claim the careful 1.1x (explorations/performance-loop/README.md, Judge a tolerance on back-to-back pairs): on a quiet host, tier-probe.mjs main against the 225,531-byte build (eager-comments.mjs --fraction 0.54, prose cat docs/*.md at 27ea216c), loopback and --network 10:100000:20000, at least 24 pairs each in two independent series, plus an A/A series (two main servers). Record as a new exp with samples. Do this before re-deriving or tightening the ceiling, or after per-file compression lands (the brief's Option E). From PR #387 review B3.
