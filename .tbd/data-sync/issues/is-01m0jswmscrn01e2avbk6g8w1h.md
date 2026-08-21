---
type: is
id: is-01m0jswmscrn01e2avbk6g8w1h
title: "metab --api <route>: any data route through the real request stack"
kind: feature
status: open
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-21-cli-parity-and-golden-coverage.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0jswnf4rw62apq363dvjrgz
  - type: blocks
    target: is-01m0jsxf4dfd6v9ncxatvm6ret
  - type: blocks
    target: is-01m0jsxff9pw8b0fmx6x3ff915
  - type: blocks
    target: is-01m0jsxft0geavafe8qygzj793
  - type: blocks
    target: is-01m0jsxg55ntr2kscwz3d5x92s
parent_id: is-01m0jsvvcqw7knvxbaq4sn6ddj
created_at: 2026-08-21T18:38:48.107Z
updated_at: 2026-08-21T18:39:16.132Z
---
One mode, complete by construction for every route now and later. Issues a GET through the in-process ASGI app with no port and no browser, waits for the index where the route needs it, and prints the normalized envelope as JSON or YAML. This is the wire-parity backbone: --walk and --diff prove their models through the library and never touch the route, which is how the nav filter shipped with unparsed query parameters and every golden still green. Ships with cli-api.tryscript.md.
