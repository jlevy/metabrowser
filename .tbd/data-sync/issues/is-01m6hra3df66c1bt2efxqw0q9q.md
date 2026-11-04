---
type: is
id: is-01m6hra3df66c1bt2efxqw0q9q
title: Document optional Git and GitHub CLI setup with a verified sign-in check
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6hr8f0x7hr7mhchrtx1sqb7
created_at: 2026-11-03T22:26:08.429Z
updated_at: 2026-11-04T17:14:29.820Z
closed_at: 2026-11-04T17:14:29.820Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
At 6b93a964, installation.md only says Git and gh are installed separately; it gives no installation/authentication verification steps or feature-specific requirements. README also says Nothing else to install for the agent skill although uv and optional Git/gh are external prerequisites. Add one concise installation section and link it from the README and PR guide: local files need neither Git nor gh; public repository URLs need admitted Git but can clone anonymously; new PR metadata needs authenticated gh; private GitHub URLs use gh credentials. Recommend a current maintained gh release, distinguish the implemented 2.81 auth-status JSON capability floor from the tbd agent installer security pin, and verify with gh auth status for the active github.com account. Stored credentials work without GH_TOKEN. No new wrapper, installer, token manager or production version-policy change. Proposed patch and primary-source audit are kept as dependency-setup-audit evidence; root applies only after current verification finishes.

## Notes

2026-11-03 read-only audit complete at6b93a964. Proposed four-file documentation patch saved as dependency-setup-audit/proposed-docs.patch; Flowmark0.3.2 and git apply --check passed, original worktree clean. Standard brew Git/gh setup, active-host auth check, stored-login support, feature-specific requirements and uv PATH guidance; no installer/wrapper, automatic setup or runtime floor change. Primary official gh/uv/Git docs verified. Root will decide/apply after current full gate; runtime/UI guidance findings belong to navigation reviewer.

2026-11-03 approved four-document setup patch applied on codex/gh-setup-01a1a051 at f324ec4f, uncommitted for coordinator integration. Added opened-repository qualifier, current macOS/Linux private-cache requirement and native Windows refusal; ordinary files remain separate. No unsupported WSL claim or separate database setup. Exact Flowmark 0.3.2, codespell, public hygiene, footer/local-link checks and git diff --check pass. Evidence: dependency-setup-audit/applied-docs.patch and applied-validation.json. Source, locks and runtime untouched by this task; full gates and commit remain coordinator-owned.
