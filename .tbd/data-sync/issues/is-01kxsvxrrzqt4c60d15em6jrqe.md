---
type: is
id: is-01kxsvxrrzqt4c60d15em6jrqe
title: Plan a standard browser contributor toolchain migration
kind: feature
status: open
priority: 2
version: 7
spec_path: TODO.md
labels:
  - build
dependencies:
  - type: blocks
    target: is-01kxshfx0fhzyccg1wwtdv7c6b
parent_id: is-01kxnx9vtb13p6z8mewgsm2t75
created_at: 2026-07-18T05:41:57.651Z
updated_at: 2026-11-20T19:15:57.775Z
extensions: {}
---
Use docs/project/research/research-2026-07-18-browser-contributor-toolchain.md. The raw-source browser build remains the baseline. Before adding dependencies, write a dedicated migration plan with before/after measures for contributor feedback, browser cost, wheel size, emitted requests, and generated-artifact reviewability. Evaluate TypeScript, Vite, and Vitest first; keep installed assets offline and same-origin; preserve the current Node contract suites and Chrome performance gates until replacements prove parity; use an isolated non-diff pilot; and review exact cooled-off packages under the disabled lifecycle-script policy.
