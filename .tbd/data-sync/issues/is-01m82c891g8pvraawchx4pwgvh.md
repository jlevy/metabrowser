---
type: is
id: is-01m82c891g8pvraawchx4pwgvh
title: "Nightly soak 2026-11-20 (run 44737855133): tests/test_ref_selector_long_list_chrome.py:179 sees 6 rows, expects 1001, on main 21dc39da7"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
created_at: 2026-11-22T19:38:12.910Z
updated_at: 2026-11-22T19:38:12.910Z
---
Nightly soak chrome (4, 3/4): assert 6 == 1001 at tests/test_ref_selector_long_list_chrome.py:179 (branch chooser long list, mb-dcp2). The chooser showed 6 branches instead of the full list once in five repetitions. Could be user-visible (truncated branch list). Find the mechanism before the 0.13.0 candidate.
