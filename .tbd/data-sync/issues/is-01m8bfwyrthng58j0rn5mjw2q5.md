---
type: is
id: is-01m8bfwyrthng58j0rn5mjw2q5
title: "Core isolation facility: one way to start, limit, and confine a child process"
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies:
  - type: blocks
    target: is-01m8bfwz44tckg3hn0sh1r7nfr
  - type: blocks
    target: is-01m8bfwztw84vfapjmyap7ta72
  - type: blocks
    target: is-01m8bfx1aaxf7qyzn1n2h1ap4v
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-26T08:35:06.138Z
updated_at: 2026-11-26T08:36:39.570Z
---
Phase 0 (plan: Isolation, The Facility; Key Decisions 6 and 11). Extract one core package, metabrowser.isolation, from builtin_plugins/pdf/preview_isolation.py (the Sandbox prefix, the probe, the isolation_for rule, the minimal environment, kill_group), render_child.limit_resources, and the supervision in sqlite_readers.py (deadline, kill grace, bounded queue answering busy, start limit, one subject per child). API at design level: Tier (separate, confined), Confinement (read, write, network, tools), Limits (cpu, address space, file size, processes), backend() probed once, launch_plan(command, tier, required, confinement, limits, environment) returning a Launch or the refusal no_sandbox, and start(plan, descriptors) in its own process group, in /, with only the named descriptors. A backend is a command prefix; the policy is data each backend renders; a caller never writes a profile. Start the PDF render child, the SQLite readers, and the Markdown child through it. No behavior change on macOS: tests/test_pdf_preview_sandbox.py, test_pdf_preview_routes.py, and the readers' and Markdown child's tests pass unchanged, with each caller's measured constants kept beside it. Update arch-threat-model.md T7 and arch-plugin-system.md to name the facility. The design and the survey of the three existing children are in the plan's Isolation section.
