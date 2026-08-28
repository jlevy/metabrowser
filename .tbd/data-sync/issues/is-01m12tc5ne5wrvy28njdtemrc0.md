---
type: is
id: is-01m12tc5ne5wrvy28njdtemrc0
title: Document the no-textual-loading-message policy in the design system
kind: feature
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m12tc1tacfnggr44ecjnb17d
created_at: 2026-08-27T23:55:07.820Z
updated_at: 2026-08-28T00:11:19.149Z
closed_at: 2026-08-28T00:11:19.148Z
close_reason: "Fixed in 101b4ad: design-system.md 'Loading States Are Shapes, Not Sentences' replaces the narrower spinner-label rule, stating skeleton-by-default, spinner-for-unknown-shape, and sr-only text as required rather than a violation."
resolution: null
duplicate_of: null
---
docs/design-system.md has loading-chrome rules (quiet period, .mb-delayed-loading, neutral spinners) but never states the policy itself: visible progress text is not used. Default is skeleton blocks carrying the shared slow pulse, as .tally-pending does; a spinner is for genuinely indeterminate waits where a block would misrepresent structure. Screen-reader-only text remains required and is explicitly not a violation. State the rule, the two forms, and how to choose.
