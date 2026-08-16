---
type: is
id: is-01kxsvxrrzqt4c60d15em6jrqe
title: "Stand up the standard front-end toolchain: TypeScript + Vite + Vitest contributor plane"
kind: feature
status: open
priority: 1
version: 3
labels:
  - build
dependencies: []
created_at: 2026-07-18T05:41:57.651Z
updated_at: 2026-08-16T08:06:33.875Z
extensions:
  linear:
    id: 848e45cb-da5f-42e2-a71a-be8cc27389f4
    linked_at: 2026-08-16T08:06:33.875Z
---
Per the reframed research-2026-07-18-diff-ui-stacks-and-browser-build-options.md: Vite 8 workspace with strict .ts sources, vite dev proxying metab serve, Vitest unit/component tests, Playwright e2e; distribution unchanged (prebuilt same-origin assets in the wheel via release-time vite build or committed dist with manifest+rebuild-diff gate). Stage it with the diff renderer as first module; typed plugin SDK package and template follow. Supersedes the buildless-ESM end-state; mb-725d remains the committed-artifact mechanism.
