---
type: is
id: is-01m6ka8sts89dbcsf9wbqsd336
title: Update manual checks for bounded binary previews and path-shaped navigation
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T12:59:14.645Z
updated_at: 2026-11-04T17:21:01.581Z
closed_at: 2026-11-04T17:21:01.581Z
close_reason: "All 17 accepted documentation findings corrected in reviewed/merged PR #298 and independently verified on its exact final-main tree. Completed against actual final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9; final independent integration review and all nine main CI jobs passed. Original evidence retains its execution pins; genuine future and release scope remains separate."
resolution: null
duplicate_of: null
---
Expanded documentation review D6: the current end-to-end manual playbook says oversized binaries stop instead of loading and uses a hash as the selected file path. Current binary rendering loads a bounded prefix with explicit cutoff information; direct file selection uses /view/<path>, while fragments select a heading or line inside a document. Correct the two manual checks without changing the product or inventing a new timing result. Independently verify against the binary handler, bytes view and navigation routes.
