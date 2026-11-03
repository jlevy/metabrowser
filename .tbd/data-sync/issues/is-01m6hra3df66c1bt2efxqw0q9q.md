---
type: is
id: is-01m6hra3df66c1bt2efxqw0q9q
title: Document optional Git and GitHub CLI setup with a verified sign-in check
kind: task
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6hr8f0x7hr7mhchrtx1sqb7
created_at: 2026-11-03T22:26:08.429Z
updated_at: 2026-11-03T22:26:15.992Z
---
At 6b93a964, installation.md only says Git and gh are installed separately; it gives no installation/authentication verification steps or feature-specific requirements. README also says Nothing else to install for the agent skill although uv and optional Git/gh are external prerequisites. Add one concise installation section and link it from the README and PR guide: local files need neither Git nor gh; public repository URLs need admitted Git but can clone anonymously; new PR metadata needs authenticated gh; private GitHub URLs use gh credentials. Recommend a current maintained gh release, distinguish the implemented 2.81 auth-status JSON capability floor from the tbd agent installer security pin, and verify with gh auth status for the active github.com account. Stored credentials work without GH_TOKEN. No new wrapper, installer, token manager or production version-policy change. Proposed patch and primary-source audit are kept as dependency-setup-audit evidence; root applies only after current verification finishes.
