---
type: is
id: is-01kzyxvf9qfc627wszts904wx3
title: "Spec: Shared file type taxonomy and bounded breakdowns"
kind: epic
status: closed
priority: 2
version: 23
spec_path: docs/project/specs/active/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md
labels:
  - file-types
  - cross-project
  - systematization
dependencies: []
child_order_hints:
  - is-01kzyzvh8t3hf2dngzbz89fg4z
  - is-01kzz02ks9eygwfy31je8z907v
  - is-01kzz02zvd18eqbqqqrnssr2qj
  - is-01kzz039dpehjrvpg7nm2e47ft
  - is-01kzz03kns6hp4a0rzkqnbjdww
  - is-01kzz03xc66nzafcd0dn48zger
  - is-01kzz045zdjskzsfrbrsx6ag23
  - is-01kzz04fp7330jyn2h03m635qc
  - is-01kzz04wegtbq1pxpq9ser4wj3
  - is-01kzz05a5ndpnvh5h1xtfzwc7q
  - is-01kzz05ksdr74fcztg1rpmj13p
  - is-01kzz05x3x3d6y2n9gzeq8xmqg
  - is-01kzz0681weprsdjnd151fxkhj
created_at: 2026-08-14T01:23:15.382Z
updated_at: 2026-08-14T03:33:43.453Z
closed_at: 2026-08-14T03:33:43.452Z
close_reason: All dependency-ordered implementation beads are complete. Metabrowser now owns and ships the shared semantic file-type registry, conserved bounded breakdown, registry-driven browser surfaces, compatibility transition, complete documentation, and future fdu adoption packet. Full make verify and manual browser validation passed; mb-me85 is a separately deferred cleanup after one supported transition cycle.
---
Deliver the Metabrowser-owned file-type registry, classification contract, conserved UI-ready breakdowns, registry-driven browser surfaces, and a versioned compatibility packet that fdu can later adopt. The linked plan defines product scope; the durable file-type contract documents define normative cross-project formats.

## Notes

Planning landed through merged PR #38 at f63ab1d. The implementation branch now ships Registry v1, Breakdown v1, schemas, conformance corpus, registry-driven Overview/navigation/Treemap surfaces, compatibility aliases, and the self-contained future fdu adoption packet. All implementation children are complete; mb-me85 separately tracks post-transition alias cleanup.
