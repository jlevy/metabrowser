---
type: is
id: is-01kzt5jxc9kpdv8n9s9dpsttts
title: "PR #32 review R2: resolve the test inventory root"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01kzt5jng86n8400av6g3z666q
created_at: 2026-08-12T05:02:11.336Z
updated_at: 2026-08-12T05:06:39.289Z
closed_at: 2026-08-12T05:06:39.289Z
close_reason: "Fixed both PR #32 review findings in b9f2ec0 with regression coverage."
---
Cursor Bugbot review thread PRRT_kwDOTX174c6YdSho. tests/test_browser_inventory_api.py:224-248 should set InventoryIndex._root to the same resolved root api_tree compares on platforms where tmp_path includes a symlink.
