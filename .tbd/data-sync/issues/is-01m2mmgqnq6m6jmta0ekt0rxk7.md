---
type: is
id: is-01m2mmgqnq6m6jmta0ekt0rxk7
title: "Phase 0C.2 review R14: permit complete cross-realm browser parser clones"
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c2
  - review
dependencies: []
parent_id: is-01m2kry0g3g8hbnhr896wvqeve
created_at: 2026-09-16T08:14:47.478Z
updated_at: 2026-09-16T08:39:43.526Z
closed_at: 2026-09-16T08:39:43.526Z
close_reason: "Fixed in b907bb2734929cd0858207ba5d73639aee168636 and formally disposed on PR #136: https://github.com/jlevy/metabrowser/pull/136#issuecomment-5694591401"
resolution: null
duplicate_of: null
---
The restricted VM harness uses deep strict equality across host and VM realms, so a valid parser returning a complete shallow or deep clone can fail only because its object prototype belongs to another realm. Normalize or compare JSON-domain values type-sensitively without prototype identity, preferably while creating parser inputs inside the restricted realm to avoid capability leaks. Add shallow/deep clone passes plus record-loss and type-change failures.

## Notes

Browser evidence now creates each parser input inside the restricted VM realm and compares JSON-domain values recursively by object keys, array shape, primitive type, and primitive value without prototype identity. Complete shallow and deep clones, including nested data, pass; record loss, in-place mutation, and integer-to-boolean changes fail. No host-realm input object or function crosses into the parser context. Validation: 19 focused browser tests passed; Ruff, BasedPyright, Biome, Flowmark, artifact checker (16 contracts/2 profiles), and diff check passed. Leave in_progress until PR disposition.
