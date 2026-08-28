---
type: is
id: is-01m12w4w0ygf4x8dxpcp5nygqn
title: "R2: accept GitHub web URLs, not only clone URLs"
kind: feature
status: open
priority: 1
version: 1
spec_path: docs/project/reviews/review-2026-08-27-delivery-order-for-status-cache-and-providers.md
labels: []
dependencies: []
parent_id: is-01m12w4tz60cps1t8d6z1v4zet
created_at: 2026-08-28T00:26:05.725Z
updated_at: 2026-08-28T00:26:05.725Z
---
Phase 1B accepts repository-root clone URLs and rejects tree/blob/commit/issue/PR URLs. The URL a person copies from the address bar is https://github.com/owner/repo/blob/main/path or /tree/main/path, so the most common input fails and reads as broken rather than bounded. Add web-URL normalization reducing /tree/<ref>/<path> and /blob/<ref>/<path> to the repository root; pure string work on a stable shape, no API or provider record, so the provider-neutral boundary holds. Carrying ref and path through as an initial selection is a follow-on. Issue and PR URLs stay out of scope but should fail naming the repository URL that would work.
