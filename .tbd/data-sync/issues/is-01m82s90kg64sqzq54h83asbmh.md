---
type: is
id: is-01m82s90kg64sqzq54h83asbmh
title: "PR #709 K4: _probe_failed set before the fetched_at check and not cleared by _forget_probes"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
labels: []
dependencies: []
parent_id: is-01m82s73za15hfvfw96fdn9e19
created_at: 2026-11-22T23:25:48.520Z
updated_at: 2026-11-22T23:45:34.424Z
closed_at: 2026-11-22T23:45:34.420Z
close_reason: "fixed in aebc9cbb9: fetched_at checked before marking failure; _forget_probes clears _probe_failed"
resolution: null
duplicate_of: null
---
Low. served_pull.py. https://github.com/jlevy/metabrowser/pull/709#pullrequestreview-6015081008
