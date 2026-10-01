---
type: is
id: is-01m3w3xzvv8g0y0hrjrs4npp8x
title: Math in a mirrored repository's Markdown shows as raw TeX under the untrusted profile
kind: feature
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-10-01T16:14:33.333Z
updated_at: 2026-10-01T16:14:33.333Z
---
Seen 2026-10-01 browsing https://github.com/jlevy/squares with the v0.12 stack tip (373b59a9): the README and SYNOPSIS.md show inline math as raw TeX, for example \(n\) and \(s(11) = T = 3.877...\), where github.com typesets math. Cause: a repository opened from a URL is forced untrusted, so Markdown renders inert (no document scripts, strict CSP), and KPress's math typesetting needs its script. Options to evaluate: typeset math on the server into MathML or static HTML before the inert allowlist (no script in the page), with the allowlist extended only to the MathML elements needed and the same allowlist-parity tests on both layers; or leave it and say so in the docs. Acceptance: a mirrored README with inline and display math typesets without any document script, the hostile-content tests still pass, and a hostile math payload cannot inject markup. Also note for the same session: a 646 KB Markdown file (SYNOPSIS.md) took roughly 5-10 seconds to render on first open, with a spinner; large-Markdown render time is the same order on main for a local folder, so this is not a regression, but it is the slowest thing in the walkthrough.
