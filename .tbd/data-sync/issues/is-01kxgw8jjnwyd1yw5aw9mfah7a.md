---
type: is
id: is-01kxgw8jjnwyd1yw5aw9mfah7a
title: Unify bootstrap paths and repository hooks
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/specs/metabrowser-v0.1.0.md
labels: []
dependencies: []
created_at: 2026-07-14T17:54:41.876Z
updated_at: 2026-07-14T17:57:58.955Z
closed_at: 2026-07-14T17:57:58.954Z
close_reason: Anchored all Codex hooks to the git root, centralized plugin-directory normalization/validation across CLI and server imports, delegated module execution to the canonical CLI before side effects, removed the duplicate legacy launcher, added three regressions, and passed the full 604-test release gate plus clean npm audit.
---
Address PR #1 review findings: anchor Codex hook scripts to the git root so subdirectory execution works; share plugin-directory normalization and validation between CLI and direct server import; and delegate python -m metabrowser.server to the canonical CLI before server import side effects. Add regressions and rerun the complete release gate.
