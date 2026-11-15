---
type: is
id: is-01m7dqrb66rkmcc23eqhx4g8vj
title: "Docs: SECURITY policy, trust model to arch-server-and-content, CONTRIBUTING and TODO"
kind: task
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7dqmd3wafkq2x9r1y2gt57v
created_at: 2026-11-14T19:15:10.661Z
updated_at: 2026-11-15T08:17:01.720Z
closed_at: 2026-11-15T08:17:01.719Z
close_reason: Implemented on claude/docs-first-principles (one standalone PR)
resolution: null
duplicate_of: null
---
Phase 1, PR 7.

- SECURITY.md (308 to about 70 lines): reporting, the served-root boundary, and a trust-settings section. CLI messages (cli/main.py:651, dotenv.py:232) and the cli-surface golden say "see SECURITY.md" for METABROWSER_ALLOWED_HOSTS and .env rules; that section must keep answering them.
- Move the content-trust model (SECURITY.md 48-308: CSP, /raw cache headers, ETags) into a new docs/project/architecture/arch-server-and-content.md with a Status line, the footer, and a project-index entry. Phase 2 completes it.
- CONTRIBUTING.md:33-34 asks for a migration plan before changing HTTP envelopes or SDK methods; AGENTS.md makes them internal contracts changed in one commit. Make CONTRIBUTING.md agree with AGENTS.md.
- TODO.md: v0.12.0 is tagged (:21 and :42 say it is not); remove replacement history (:22, :54, :88, :93, :98-99).
