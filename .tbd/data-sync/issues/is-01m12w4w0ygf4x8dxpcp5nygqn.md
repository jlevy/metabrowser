---
type: is
id: is-01m12w4w0ygf4x8dxpcp5nygqn
title: "R2: accept GitHub web URLs, not only clone URLs"
kind: feature
status: closed
priority: 1
version: 2
spec_path: docs/project/reviews/review-2026-08-27-delivery-order-for-status-cache-and-providers.md
labels: []
dependencies: []
parent_id: is-01m12w4tz60cps1t8d6z1v4zet
created_at: 2026-08-28T00:26:05.725Z
updated_at: 2026-08-28T02:28:23.518Z
closed_at: 2026-08-28T02:28:23.517Z
close_reason: "Done in f46bc26: Phase 1B now reduces provider web URLs to a clone URL plus a selection, with a variants table (tree/blob/raw/blame/commit/releases/raw.githubusercontent), a carried-vs-dropped table for fragments and query strings, post-clone resolution of the ambiguous ref/path split, and PR URLs retaining the number for the later provider view."
resolution: null
duplicate_of: null
---
Phase 1B accepts repository-root clone URLs and rejects tree/blob/commit/issue/PR URLs. The URL a person copies from the address bar is https://github.com/owner/repo/blob/main/path or /tree/main/path, so the most common input fails and reads as broken rather than bounded. Add web-URL normalization reducing /tree/<ref>/<path> and /blob/<ref>/<path> to the repository root; pure string work on a stable shape, no API or provider record, so the provider-neutral boundary holds. Carrying ref and path through as an initial selection is a follow-on. Issue and PR URLs stay out of scope but should fail naming the repository URL that would work.
