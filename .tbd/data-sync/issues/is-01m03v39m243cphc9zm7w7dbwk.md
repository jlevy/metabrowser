---
type: is
id: is-01m03v39m243cphc9zm7w7dbwk
title: Document 'effortlessly fast' as a core MetaBrowser design principle
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m03tqjzm7j6qkxjeath5qe0d
created_at: 2026-08-15T23:11:18.138Z
updated_at: 2026-08-16T00:00:51.368Z
closed_at: 2026-08-16T00:00:51.367Z
close_reason: null
---
State clearly in the design docs: everything in MetaBrowser should be effortlessly fast, without compromise. Default posture is to prefetch all data a user might plausibly need next (unless there is a significant foreseeable cost), and no loading state should be perceptible in the common case. Related implementation beads: prefetch subfolder listings, and the ~50ms spinner-delay rule.
