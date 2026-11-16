---
type: is
id: is-01m7hh0msx7cfhs3hqfw6fq9e3
title: "PR #466 A2: assemble_grouped_tree checks its row bound only after a group's pages"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjpsxhfvt5ms7769smjwf
hold: null
hold_until: null
created_at: 2026-11-16T06:34:20.348Z
updated_at: 2026-11-16T07:26:33.008Z
started_at: 2026-11-16T06:34:32.815Z
closed_at: 2026-11-16T07:26:33.007Z
close_reason: "fixed in 311c0db (per-page row bound, bounds test, route case past the page bound); PR #466 review A"
resolution: null
duplicate_of: null
---
Medium. tree_page_assembly.py:219-260. Review A https://github.com/jlevy/metabrowser/pull/466#pullrequestreview-5915498910. Fix: check per page; bounds test beside test_tree_page_assembly_enforces_page_and_row_bounds; route case past INVENTORY_TREE_PAGE_ROWS.
