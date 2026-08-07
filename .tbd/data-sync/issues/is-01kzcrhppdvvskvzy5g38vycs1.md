---
type: is
id: is-01kzcrhppdvvskvzy5g38vycs1
title: "Quick File results: bold filename, muted regular-weight parent path"
kind: task
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01kzcr7qzp4j0x9h694b8evywa
created_at: 2026-08-07T00:04:12.620Z
updated_at: 2026-08-07T00:10:01.970Z
closed_at: 2026-08-07T00:10:01.970Z
close_reason: "Implemented on feat/quick-file-palette (PR #22): chrome typography rule documented in styles.css with an enforced exception list, .kbd component added and applied, T bound alongside /, palette rows restyled to the file-header weight hierarchy. make verify green."
---
In the Quick File pop-over, each result row should read with the same weight hierarchy the rest of the chrome uses.

- filename (.search-palette-label): bold, matching .file-header-path in the chrome around the file view, which is var(--weight-bold) at var(--nav-font-size) in var(--text)
- parent path (.search-palette-description): regular weight and muted grey, the way gitignored entries read in the nav panel

Today the label is var(--weight-medium) and the description declares no weight, so it inherits.

Note on the grey: nav gitignored rows dim the whole row with opacity: 0.45 because they fade icon, age, and size together. A single line of secondary text expresses the same intent through var(--muted) at var(--weight-normal), which is the semantic token for muted chrome text. Do not copy the opacity mechanism.
