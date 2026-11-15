---
type: is
id: is-01m7dqra8mf0zt47bay4m8mvts
title: "Docs: browsing-history guide; cut command-line and PR review guides to their subjects"
kind: task
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7dqmd3wafkq2x9r1y2gt57v
created_at: 2026-11-14T19:15:09.715Z
updated_at: 2026-11-15T05:56:37.380Z
---
Phase 1, PR 5.

- New docs/browsing-history.md (about 150 lines): the Commits tab, /commit/<rev> pages, ranges, --diff, and --diff-check.
- docs/command-line.md (1,025 to about 450 lines): every mode and option. Document --base-port, --ssh-options, --gcp, --zone, and --project (cli/main.py:181-186, 754-773) and that the remote host needs metab installed (cli/remote.py). Add a configuration file and environment variable reference. Internals become links to arch-repository-sources-and-provider-mirrors.md, moving only what it lacks: mirror refresh and pin routes (194-272), clone progress (292-329), mirror page naming (331-370), the beside-a-checkout table (719-766), application-home repair (809-820). --exit-on-eof internals (132-170) go to the docstring of the function that does it. Title-case the H2s at :274 and :999. Keep the path (the CLI's help links it) and the #pull-requests anchor (installed skills link it).
- docs/reviewing-pull-requests.md (540 to about 300 lines): background preparation (42-72) and cache refusals (359-372) to the repository document; styling (180-186) cut where the design system's pull-request page section already says it. It owns the failure-reason table; command-line.md links it.
- Add README links.
