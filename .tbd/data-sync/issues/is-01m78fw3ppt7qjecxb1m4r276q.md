---
type: is
id: is-01m78fw3ppt7qjecxb1m4r276q
title: Repository plugin discovery and trust levels
kind: task
status: open
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies:
  - type: blocks
    target: is-01m78gmwnk00rz776w8w8k7g9j
  - type: blocks
    target: is-01m78fw226k1aejzey9xamd4e7
  - type: blocks
    target: is-01m78fwdh6mt5frdg94thadjkh
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:13.301Z
updated_at: 2026-11-12T18:47:17.901Z
---
Phase 2 (plan: Repository Plugins). Automatic discovery of the served folder's repository plugins: the repository is the Git top level containing the served folder (its repository context) or the folder itself outside Git; its environment is the nearest uv project or workspace root's .venv (or [tool.metabrowser.plugins] environment); plugins are read as data from each *.dist-info/entry_points.txt (metabrowser.plugins), direct_url.json for provenance (this repository vs a library with distribution and version), workspace members' pyproject.toml (known before uv sync), and .metabrowser/plugins/*/manifest.toml; optional include/exclude/dirs config. Bounded reads, no interpreter before trust, cached by fingerprint. Trust levels recorded in plugins.yml: undecided (default: report only, serve nothing), trusted (path, VS Code / mise style; covers later pulls, new plugins, lock bumps), pinned (approved commit + plugin-set SHA-256, direnv style; any change loads nothing until Review shows the diff since the approved commit and the user approves), denied; parent-folder records with nearest-wins; a changed origin URL resets to undecided. Modes: ROOT --plugins-trust [--pinned], --plugins-deny, --plugins-untrust, --plugins-trust DIR, and per-command --repo-plugins (records nothing; for CI and authors). Never for Git sources from URLs, pins, mirrors, pull-request pages, --untrusted, or the cache home. Missing environment: report uv sync --locked. The bar's model in GET /api/plugins; --doctor given a root reports why each plugin is or is not loaded. Goldens for each level on a fixture repository. Supersedes the declaration-file design and mb-m1mw.

## Notes

Review (2026-11-12, independent design review; plan updated to match): Parent-folder trust covers only the origin patterns it names (e.g. github.com/example-org/*); any other repository under it is undecided. Under Trusted, library plugins load only from direct dependencies of workspace members; transitive ones are reported until include names them. Own repository reader: nearest .git no higher than home, ownership-checked, origin from the common dir config for any host (repository_context answers only GitHub and checks no ownership). Plugin set hash covers every editable install's source tree, .pth files, uv.lock, and .metabrowser/; Review/--dry-run print it and Approve/--yes take --expect SHA256; store full commit ids. Repository sources may not use built-in plugin names. Parent trust command is --plugins-trust-under DIR --origins PATTERN.
