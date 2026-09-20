---
type: is
id: is-01m2zvfm9pdxz0emydeqedf9gq
title: "S209-7: a browsed repo's .env can set METABROWSER_PLUGINS_DIRS and load plugin JavaScript into the app origin"
kind: bug
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr209
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T16:48:10.032Z
updated_at: 2026-09-20T16:48:10.032Z
---
Found while fixing mb-nisk. The dotenv chain walks up from cwd, so 'cd cloned-repo && metab .' honors that repo's .env. METABROWSER_PLUGINS_DIRS is still accepted from it, and tests/test_dotenv_loading.py test_dotenv_drives_plugin_discovery pins that as intended. A repository can therefore point plugin discovery at a directory inside itself; plugin JavaScript runs in the application origin with full /api access, which is strictly more than the /raw sandbox lift closed by mb-nisk, and it predates PR 209 (present on main). Needs a design decision: refuse the key from dotenv entirely, refuse it when the dotenv file lies inside the served root, or refuse it under --untrusted. Reverses documented behavior, so it changes docs and that test.
