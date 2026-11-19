---
type: is
id: is-01m0k3nrtdd1dhyj0bvnf440s2
title: Vendor Mermaid 12.3.0 ESM build with a directory-shaped vendor entry
kind: task
status: closed
priority: 1
version: 11
spec_path: docs/project/specs/active/plan-2026-08-21-mermaid-diagram-rendering.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m0k3ns7dh5qtb3p5erjnqsvf
parent_id: is-01m0k3nbmdvy9x8g3r8t9ckzjt
hold: null
hold_until: null
created_at: 2026-08-21T21:29:48.621Z
updated_at: 2026-11-19T02:37:05.862Z
started_at: 2026-11-19T01:37:39.426Z
closed_at: 2026-11-19T02:37:05.861Z
close_reason: Done on branch claude/mermaid-diagram-rendering-441fe6 (commit 4e0bc6391)
resolution: null
duplicate_of: null
---
GitHub's renderer bundle embeds Mermaid 12.3.0 (read 2026-11-18); 12.3.0 was published 2026-11-03, past the 14-day cool-off. Its ESM build is mermaid.esm.min.mjs (30,936 bytes) plus chunks/mermaid.esm.min/*.mjs (105 files, 5,404,632 bytes; largest elk-*.mjs 1,620,399). Add a directory-shaped VendorEntry in devtools/vendor_assets.py that copies the tree without .map files and hashes each file into manifest.json; pin mermaid 12.3.0 in package.json; NOTICE.md and license. Raise TOTAL_CAP_BYTES with the measurement beside it; PER_FILE_CAP_BYTES stays 1,700,000.
