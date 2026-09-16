---
type: is
id: is-01m2mmctkaezwfx0rq66tqafyp
title: "Phase 0C.2 review R11: close host-realm escape in browser parser sandbox"
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c2
  - review
dependencies: []
parent_id: is-01m2kry0g3g8hbnhr896wvqeve
created_at: 2026-09-16T08:12:39.401Z
updated_at: 2026-09-16T08:12:43.574Z
---
The restricted browser evidence injects host-realm constructors such as TextEncoder, URL, and structuredClone into the VM context. A parser can recover Node process through a constructor chain and receive a false browser-portability proof. Remove host-realm constructor capabilities by using an actual browser runtime or context-native safe browser primitives with dynamic code disabled. Add regressions for constructor-chain recovery through every exposed capability while keeping the installed hosted-review parser green.
