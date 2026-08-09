---
type: is
id: is-01kzksypskm2xsm8bmesrpttf2
title: "PR #22 review R6: bulk apply can downgrade completeness after markComplete (known_file_catalog.js:216-219)"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01kzksyn1g7gqhyw86ssr1gfvt
created_at: 2026-08-09T17:43:28.306Z
updated_at: 2026-08-09T17:43:28.306Z
---
Bugbot 3742621184, Medium. Real race: bulk built mid-walk (complete:false) can resolve after capability.update marked complete, permanently downgrading the flag (the completion event will not fire again). Fix: applyBulkSnapshot raises completeness only (clear() still resets it); document the restart trade-off.
