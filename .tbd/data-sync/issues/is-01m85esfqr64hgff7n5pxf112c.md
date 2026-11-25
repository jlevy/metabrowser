---
type: is
id: is-01m85esfqr64hgff7n5pxf112c
title: "Doctor: show the first-clone reserve, its source, and the largest clone that fits"
kind: task
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-24T00:20:17.130Z
updated_at: 2026-11-25T03:58:39.282Z
closed_at: 2026-11-25T03:58:39.276Z
close_reason: "Duplicate of mb-bhwq (both are PR #768 finding A9)."
resolution: null
duplicate_of: null
---
Review A9 on PR 768: at 1.04 GB free the cache check reports ok while only ~35 MB repositories fit. Add details rows to the cache check: the reserve (METABROWSER_CACHE_RESERVE_MB or default), and the largest GitHub-reported size a first clone could still take (free - reserve, divided by PACK_PER_REPORTED). Pin in tests/test_doctor.py and the doctor golden.
