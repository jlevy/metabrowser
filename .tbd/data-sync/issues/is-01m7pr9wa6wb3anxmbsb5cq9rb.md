---
type: is
id: is-01m7pr9wa6wb3anxmbsb5cq9rb
title: "Recent targets: write a mirror's target, its web URL, from ProviderUrlReducer.web_url once #540 lands"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md
labels: []
dependencies: []
parent_id: is-01m7nnxhaqce1g2ewec3wbaf7e
created_at: 2026-11-18T07:17:55.141Z
updated_at: 2026-11-20T17:23:04.205Z
---
#546 (mb-40k4) added an entry's optional target, where an open pointed, as the open-modes design asks (docs/project/architecture/arch-open-modes.md, #558). A folder writes it (the file or --path named); a mirror's is read, checked to lie inside its root, and kept, but not written, because the canonical web URL is rebuilt from the URL grammar's selection by ProviderUrlReducer.web_url, which #540 adds, and #546 did not add a second function for it. Do: pass web_url(source.normalized, selection) as the target from run_serve_pin (cli/git_pin_cli.py, via serve_until_interrupted) and from recent_cli.add_recent; add the case to tests/golden/cli-recent.tryscript.md; then Open Recent can reopen a pull request (the app passes the target to metab) and Open URL… can offer recent GitHub targets (mb-m4mg).
