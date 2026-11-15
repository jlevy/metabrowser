---
type: is
id: is-01m7dqraqkhmybm70qscw1hrzy
title: "Docs: working-with-agents guide and skill update"
kind: task
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7dqmd3wafkq2x9r1y2gt57v
created_at: 2026-11-14T19:15:10.194Z
updated_at: 2026-11-15T08:17:01.328Z
closed_at: 2026-11-15T08:17:01.327Z
close_reason: Implemented on claude/docs-first-principles (one standalone PR)
resolution: null
duplicate_of: null
---
Phase 1, PR 6.

- New docs/working-with-agents.md (about 150 lines): installing the skill; the loop in which an agent serves a path or a pull-request URL (--no-open) and hands you the page; agent-log JSONL timelines (the agent_log manifest lists Claude Code, Gemini, and Pi); --api, --show, and --walk for agents. No sandbox settings until metab --present ships.
- skills/metabrowser/SKILL.md: add Commits, /commit/<rev>, --diff, live logs, and handing the user any page; cut the pull-request section (71-131) to its commands and a link. Keep the absolute links installed skills use (docs/reviewing-pull-requests.md and docs/command-line.md#pull-requests).
- Add README links.
