---
type: is
id: is-01m0k3nrtdd1dhyj0bvnf440s2
title: Vendor Mermaid 11.17.0 ESM build with a directory-shaped vendor entry
kind: task
status: open
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-08-21-mermaid-diagram-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0k3ns7dh5qtb3p5erjnqsvf
parent_id: is-01m0k3nbmdvy9x8g3r8t9ckzjt
created_at: 2026-08-21T21:29:48.621Z
updated_at: 2026-08-21T22:08:25.510Z
---
devtools/vendor_assets.py currently vendors single flat files (ENTRIES is a tuple of VendorEntry with one dest each). Mermaid's ESM build is mermaid.esm.min.mjs (30,255 bytes) plus chunks/mermaid.esm.min/*.mjs (103 files, 3,491,470 bytes). Add a directory-shaped entry that copies and hashes the tree, pin mermaid 11.17.0 in package.json, add the NOTICE.md entry (MIT).

Raise TOTAL_CAP_BYTES from 3,000,000; the measured tree is 3,521,725 bytes against a present vendored total of 432,092. Record the measurement beside the constant. Leave PER_FILE_CAP_BYTES at 1,700,000: the largest chunk is 705,086 bytes.

Every import and dynamic import in the build is relative, so no import map is needed. Packaging cost: src/metabrowser is 948,476 bytes zipped today; the tree adds 1,018,858 bytes zipped.
