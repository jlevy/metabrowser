---
type: is
id: is-01m3aghkeb2jnz3q6dqpjnefbe
title: "tests/dom/render-view.js is broken and unused: port the ES module loader or delete it"
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-09-24T20:08:39.113Z
updated_at: 2026-09-24T20:08:39.113Z
---
Found in round 2 reviews: tests/dom/render-view.js has failed at load since before v0.12 work (it never loads resource-context.js and inventory-scope.js, and loads built-in plugins as plain scripts although they are ES modules, so SyntaxError at builtin/binary/index.js). Nothing runs it. Either port tests/dom/load-plugins.js's module loader into it and run it from a test, or delete it.
