---
type: is
id: is-01m87spnq3hdm7tr8cfmp4cp41
title: Evaluate the diagram frame's allow-scripts allow-same-origin
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/architecture/arch-threat-model.md
labels:
  - security
dependencies: []
created_at: 2026-11-24T22:09:28.289Z
updated_at: 2026-11-24T22:09:28.289Z
---
Threat model T1. builtin_plugins/markdown/diagram-frame.js lays out untrusted Mermaid in an about:srcdoc frame sandboxed allow-scripts allow-same-origin, so it runs in the application's origin; containment rests on the frame's meta CSP and Mermaid's sanitizing. Decide whether the frame can drop allow-same-origin (an opaque origin), and what measuring needs from the parent.
