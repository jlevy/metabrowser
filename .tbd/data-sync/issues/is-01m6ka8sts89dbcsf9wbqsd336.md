---
type: is
id: is-01m6ka8sts89dbcsf9wbqsd336
title: Update manual checks for bounded binary previews and path-shaped navigation
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T12:59:14.645Z
updated_at: 2026-11-04T12:59:14.645Z
---
Expanded documentation review D6: the current end-to-end manual playbook says oversized binaries stop instead of loading and uses a hash as the selected file path. Current binary rendering loads a bounded prefix with explicit cutoff information; direct file selection uses /view/<path>, while fragments select a heading or line inside a document. Correct the two manual checks without changing the product or inventing a new timing result. Independently verify against the binary handler, bytes view and navigation routes.
