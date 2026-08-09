---
type: is
id: is-01kzj9trwqbkxdfse1bbw8m6j2
title: Exclude gitignored files from crawl and Quick File navigation
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-08-09T03:42:27.734Z
updated_at: 2026-08-09T03:42:27.734Z
---
Crawl and allow navigation of all files, but never include gitignored ones. Global setting eventually; hardcoded for now is acceptable.

Raised 2026-08-07 alongside the complete-coverage work and not yet implemented.

Scope to settle while implementing:
- whether the exclusion happens at the walker/inventory level (never indexed) or at the catalog/search level (indexed, then filtered out of Quick File). The inventory currently carries a gitignored flag rather than dropping entries, and the tree paints gitignored rows dimmed, so dropping them from the index would change the Files tree too.
- the observed count in the palette status must reflect the searchable set, not the raw index, or it overstates coverage.

Pairs with mb-hj78: whatever bulk path feed lands should carry only the searchable set. Depends on the direction chosen in mb-ci04.
