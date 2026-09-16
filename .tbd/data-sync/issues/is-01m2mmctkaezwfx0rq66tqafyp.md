---
type: is
id: is-01m2mmctkaezwfx0rq66tqafyp
title: "Phase 0C.2 review R11: close host-realm escape in browser parser sandbox"
kind: bug
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c2
  - review
dependencies: []
parent_id: is-01m2kry0g3g8hbnhr896wvqeve
created_at: 2026-09-16T08:12:39.401Z
updated_at: 2026-09-16T08:26:08.332Z
---
The restricted browser evidence injects host-realm constructors such as TextEncoder, URL, and structuredClone into the VM context. A parser can recover Node process through a constructor chain and receive a false browser-portability proof. Remove host-realm constructor capabilities by using an actual browser runtime or context-native safe browser primitives with dynamic code disabled. Add regressions for constructor-chain recovery through every exposed capability while keeping the installed hosted-review parser green.

## Notes

Implemented a no-host-value browser evidence VM in devtools/artifact-contract-browser-check.mjs. The context uses vm.constants.DONT_CONTEXTIFY, disables string and WebAssembly code generation, forbids imports, and bootstraps only context-native TextEncoder, one-shot UTF-8 TextDecoder, atob, and btoa. Corpus inputs are created inside the VM realm; no host object or function is exposed. A regression attempts process recovery through the input, every added browser capability, representative ECMAScript constructors, and globalThis; the parser now fails with the expected blocked-escape diagnostic while all installed hosted-review parsers pass. Docs name the exact boundary. Validation: 19 focused browser tests passed; Ruff, BasedPyright, Biome, Flowmark, artifact checker (16 contracts/2 profiles), and diff check passed. Leave in_progress until PR disposition.
