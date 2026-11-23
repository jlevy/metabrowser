---
type: is
id: is-01m83cdt49bjjcj8afcc8j9faw
title: "PR #722 A5: record the cost of a deep request, or trim the full child sorts"
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m836qya23kghgk2m3t9em8nc
created_at: 2026-11-23T05:00:28.678Z
updated_at: 2026-11-23T05:00:35.347Z
closed_at: 2026-11-23T05:00:35.328Z
close_reason: "fixed: in `135c3bc96`: each expanded folder selects its leading children with `heapq.nsmallest` instead of sorting all; 0.36 s to 0.09 s CPU for a 100k-file folder at level 10 with byte-identical output, recorded beside `ROLLUP_MAX_DEPTH`; confirmed by `test_selected_children_and_rest_match_a_full_sort` over 6 budgets and an 18,000-query differential run"
resolution: null
duplicate_of: null
---
Review A on https://github.com/jlevy/metabrowser/pull/722, finding A5 (suggestion): record the cost of a deep request, or trim the full child sorts.
