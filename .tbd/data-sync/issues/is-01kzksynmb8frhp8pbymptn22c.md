---
type: is
id: is-01kzksynmb8frhp8pbymptn22c
title: "PR #22 review R2: Enter acts on held rows during searching (search_palette.js:383-391)"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01kzksyn1g7gqhyw86ssr1gfvt
created_at: 2026-08-09T17:43:27.114Z
updated_at: 2026-08-09T17:49:48.037Z
closed_at: 2026-08-09T17:49:48.035Z
close_reason: "Rebutted: hold-rows branch returns before results reassignment so DOM and accepted array agree; visible-rows-actionable is the tested contract; ETag revalidation covers vanished files. Replied and resolved on the thread."
---
Bugbot 3732899480, Medium. Claim: Enter/click act on stale results while new search pending. Assessment: rows are held ONLY when the new composition is empty+searching, and the results array is not reassigned then — DOM and results agree; visible rows are actionable by design (tested contract). Candidate for rebuttal.
