---
type: is
id: is-01kz2hv96ex78x8yxsmgam52ys
title: Align the Metabrowser agent skill with cli-agent-skill-patterns
kind: task
status: closed
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-08-03T00:54:42.125Z
updated_at: 2026-08-03T01:06:01.549Z
closed_at: 2026-08-03T01:06:01.549Z
close_reason: Skill now local-first with the pinned uvx fallback, declares compatibility, documents a reproducible pinned install form, and has PR-time pin-drift tests.
---
Review found the skill is a correct L1 CLI-backed skill with strong release-time pin coordination. Gaps: (1) SKILL.md prefers the uvx runner over a local metab, inverting the guideline's local-first rule; (2) pin drift is only caught at release, not on PRs; (3) no reproducible pinned install form is documented; (4) no compatibility frontmatter declaring the uv requirement.
