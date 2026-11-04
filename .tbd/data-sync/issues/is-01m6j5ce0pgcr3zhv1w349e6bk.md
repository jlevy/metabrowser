---
type: is
id: is-01m6j5ce0pgcr3zhv1w349e6bk
title: Make branch chips copyable on hover and keyboard focus
kind: task
status: in_progress
priority: 1
version: 3
spec_path: docs/design-system.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6j4m8h98qy2w5w5wj5d46gj
hold: null
hold_until: null
created_at: 2026-11-04T02:14:36.294Z
updated_at: 2026-11-04T02:28:29.856Z
started_at: 2026-11-04T02:28:29.856Z
---
Owner requests a tiny click-to-copy icon when hovering branch names in most locations. Reuse shared branch-chip/copy primitives and existing clipboard ownership/security helpers. Reveal on hover and focus-visible without layout shifts; exact underlying branch/ref text, accessible labels and success feedback, no row navigation on copy. Preserve dropdown/menu semantics and avoid nested interactive controls; use eligible locations or sibling control placement. Audit Git history, PR metadata/list, source selector and other branch surfaces together with mb-12tf. No new clipboard framework or dependency.
