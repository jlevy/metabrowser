---
type: is
id: is-01kxsvxrrzqt4c60d15em6jrqe
title: Plan a standard browser contributor toolchain migration
kind: feature
status: open
priority: 1
version: 4
labels:
  - build
dependencies: []
created_at: 2026-07-18T05:41:57.651Z
updated_at: 2026-08-27T05:35:00.976Z
extensions:
  linear:
    id: 848e45cb-da5f-42e2-a71a-be8cc27389f4
    linked_at: 2026-08-16T08:06:33.875Z
---
Use docs/project/research/research-2026-07-18-browser-contributor-toolchain.md. The raw-source browser build remains the baseline. Before adding dependencies, write a dedicated migration plan with before/after measures for contributor feedback, browser cost, wheel size, emitted requests, and generated-artifact reviewability. Evaluate TypeScript, Vite, and Vitest first; keep installed assets offline and same-origin; preserve the current Node contract suites and Chrome performance gates until replacements prove parity; use an isolated non-diff pilot; and review exact cooled-off packages under the disabled lifecycle-script policy.
