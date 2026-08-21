---
type: is
id: is-01m0k63zme8wetezbbq59ys3k8
title: One file-type source of truth, in YAML, mirroring linguist
kind: epic
status: closed
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-08-21-file-type-source-of-truth.md
labels: []
dependencies: []
child_order_hints:
  - is-01m0k52aba17zgc5njavnj58xq
  - is-01m0k52aw4w2bn7f7zfbfswdk5
  - is-01m0k64nnv04391778m8e1yad2
  - is-01m0k64p0t4x4vn9hb6bm99adv
  - is-01m0k65ab493q97zpw6hgcjjsc
created_at: 2026-08-21T22:12:31.501Z
updated_at: 2026-08-21T23:49:52.489Z
closed_at: 2026-08-21T23:49:52.487Z
close_reason: "Landed. The registry declares one number per family — its hue — with the linguist language and its upstream color recorded beside it for provenance. Source stayed TOML rather than moving to YAML: Rust tooling is planned and TOML is better supported there. Lightness and chroma belong to the theme, one pair for the whole palette, resolved server-side because a browser clips out-of-gamut oklch and moves hue by up to 9 degrees. Spec: docs/project/specs/active/plan-2026-08-21-file-type-source-of-truth.md"
---
What a file is — its family, its label, its color, the extensions and basenames that identify it — should be declared once and read from everywhere. Most of it already lives in recommended-file-types.toml. The part a reader notices first does not: color is decided in the browser by hashing a family name into a pool of twelve slots, for 56 families.

This epic moves the source to YAML, adds the fields that make it the whole declaration, and takes GitHub's language colors as the starting point so a reader who knows JavaScript is yellow does not relearn the vocabulary here.

Measured: 688 languages in linguist carry a color; 38 of our 56 families map directly; 18 are not languages and need our own. Upstream also settles the complaint that started this, CSS #663399 against Markdown #083fa1.

Spec: docs/project/specs/active/plan-2026-08-21-file-type-source-of-truth.md
