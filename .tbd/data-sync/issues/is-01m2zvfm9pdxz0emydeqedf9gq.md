---
type: is
id: is-01m2zvfm9pdxz0emydeqedf9gq
title: "S209-7: a browsed repo's .env can set METABROWSER_PLUGINS_DIRS and load plugin JavaScript into the app origin"
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr209
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T16:48:10.032Z
updated_at: 2026-09-21T07:44:41.139Z
closed_at: 2026-09-21T07:44:41.138Z
close_reason: "Merged to main as f08ad3d4 (PR 223). METABROWSER_PLUGINS_DIRS joins the capability variables and METABROWSER_ALLOWED_HOSTS in the dotenv REFUSED_KEYS, so a repository browsed from inside itself can no longer make the served root an automatic plugin source, which docs/plugins.md already named as a security boundary. The process environment and --plugins-dir are unchanged. The test that pinned the old behaviour is inverted rather than deleted and now asserts both halves end to end. Other variables were reviewed: HOST/PORT are only read by smoke_probes, DEBUG sits behind the same-origin gate and 404s unless set, and the rest carry no trust consequence; METABROWSER_HOME deserves the same refusal and is handled on the stack layer that introduces the cache."
resolution: null
duplicate_of: null
---
Found while fixing mb-nisk. The dotenv chain walks up from cwd, so 'cd cloned-repo && metab .' honors that repo's .env. METABROWSER_PLUGINS_DIRS is still accepted from it, and tests/test_dotenv_loading.py test_dotenv_drives_plugin_discovery pins that as intended. A repository can therefore point plugin discovery at a directory inside itself; plugin JavaScript runs in the application origin with full /api access, which is strictly more than the /raw sandbox lift closed by mb-nisk, and it predates PR 209 (present on main). Needs a design decision: refuse the key from dotenv entirely, refuse it when the dotenv file lies inside the served root, or refuse it under --untrusted. Reverses documented behavior, so it changes docs and that test.
