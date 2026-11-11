---
type: is
id: is-01m74vxes42hfn862g7ena2qc7
title: "PR #347 B3: keep _DOCUMENT_BYTES small rather than raising it to the shell's bound"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m74vwmegp0f11eb7vj9pnq0t
created_at: 2026-11-11T08:34:42.596Z
updated_at: 2026-11-11T09:41:56.914Z
closed_at: 2026-11-11T09:41:56.914Z
close_reason: "fixed in ecdaaa51: document bound kept at 64 KiB with a 16,384-opener budget, both measured; optional semaphore declined"
resolution: null
duplicate_of: null
---
Severity: Suggestion. PR #347 review B round 1 at 8dd80d0c (https://github.com/jlevy/metabrowser/pull/347#pullrequestreview-5855525387). References: pull_snapshot.py:52-55, :326-335.
