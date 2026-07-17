---
type: is
id: is-01kxgt78vc6pr042rbf4e9jn0f
title: Normalize CLI environment paths and browser opening
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-07-14-metabrowser-v0.1.0-standalone-package.md
labels: []
dependencies: []
created_at: 2026-07-14T17:19:01.995Z
updated_at: 2026-07-17T21:16:40.237Z
closed_at: 2026-07-14T17:23:10.193Z
close_reason: Normalized and validated plugin-directory configuration through one shared CLI helper, loaded dotenv before walk logging, replaced the macOS-only remote opener with webbrowser, added three regressions, and passed the complete 598-test release gate plus clean npm audit.
---
Address PR #1 review findings for standalone CLI consistency: normalize all METABROWSER_PLUGINS_DIRS entries before serve imports the server, load the common dotenv chain before walk applies environment-backed configuration, and replace the macOS-only remote browser launcher with Python's portable webbrowser API. Add regression coverage and rerun the full release gate.
