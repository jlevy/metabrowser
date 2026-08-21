---
type: is
id: is-01m0jsvvcqw7knvxbaq4sn6ddj
title: "CLI parity: every model reachable from metab, every one pinned by a golden"
kind: epic
status: open
priority: 1
version: 14
spec_path: docs/project/specs/active/plan-2026-08-21-cli-parity-and-golden-coverage.md
labels: []
dependencies: []
child_order_hints:
  - is-01m0jswmemndr1tmamb5zn5w61
  - is-01m0jswmscrn01e2avbk6g8w1h
  - is-01m0jswn4dgygrcgnzz5g2mbtj
  - is-01m0jswnf4rw62apq363dvjrgz
  - is-01m0jswnx3xp7xegyxnk3a2bv9
  - is-01m0jsxesr35r0d8rkrar80nex
  - is-01m0jsxf4dfd6v9ncxatvm6ret
  - is-01m0jsxff9pw8b0fmx6x3ff915
  - is-01m0jsxft0geavafe8qygzj793
  - is-01m0jsxg55ntr2kscwz3d5x92s
  - is-01m0jsxgfznxwn8cwr2n3p01f4
  - is-01m0jsxgty51qvw61s6sfwv688
created_at: 2026-08-21T18:38:22.102Z
updated_at: 2026-08-21T18:39:37.614Z
extensions:
  linear:
    id: 21c3ee1a-cf78-4125-9ff3-6e9a4ff80b80
    linked_at: 2026-08-21T18:39:37.613Z
---
Every model the browser draws should be reachable from `metab` without a browser or a listening port, and every one that is reachable should be pinned by a golden transcript. Today two of eleven data surfaces meet that bar.

The principle is drawn on the layering this codebase already has — route, kind, model, view. Three of those four layers are data and need no screen; only the view does. So parity is stated at the model layer, and the view layer is exempt with an enumerated list of what that covers and where it is tested instead.

The gap that matters most is /api/file: it carries the kind and the view list for every selection, so the tabs a reader sees are decided there, and nothing outside a browser proves that README.md opens as markdown with Document and Source.

A second finding shapes the design. `--walk` and `--diff` reach their models through the library, not the route, so they prove the model and not the wire. A route can accept a parameter the library never sees, or drop an envelope key, with every existing golden still green — which is what happened when the nav filter shipped.

The work is a `--api <route>` mode through the real ASGI stack, a `--show <path>` mode reporting the four layers for one selection, one normalizer stating which fields are stable, a parity column in the map document, and a check in `make lint` that fails when a registered route, kind, or view has no CLI equivalent or no golden.

Spec: docs/project/specs/active/plan-2026-08-21-cli-parity-and-golden-coverage.md
