---
type: is
id: is-01m1mva1cks2ky43dnbspjry5f
title: "PR #101 R6b: delete the fdu-inventory-adapter spike, per its own disposition"
kind: task
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m1mv8fds3d80zj3qmg1cct9b
created_at: 2026-09-03T23:57:46.258Z
updated_at: 2026-09-08T00:02:49.447Z
closed_at: 2026-09-08T00:02:49.446Z
close_reason: "Chose a rerunnable historical spike: README keeps adapter.py with run.py and evidence, explicitly outside the shipped provider/distribution. This removes the contradictory delete instruction without breaking the preserved harness."
resolution: null
duplicate_of: null
---
DEFERRED, not done: the disposition contradicts itself. explorations/fdu-inventory-adapter/README.md says to keep probe.py, run.py, the README, and evidence.json as the reproducible Phase 3A record, and to delete adapter.py — but run.py:26 does 'from adapter import FduSpikeBackend'. Deleting adapter.py leaves a kept file with a broken import. Decide which the record actually is: if run.py is a re-runnable harness, adapter.py stays; if it is a written record of how the measurement was taken, delete both and say so in the README. pyproject.toml:191 already excludes the directory from type checking, so nothing enforces either answer today.
