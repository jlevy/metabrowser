---
type: is
id: is-01m7p2h9n62dqsw4kcbcwba0qr
title: Remove the Markdown mount's unused browser-side includeToc option (#517 review A6)
kind: task
status: open
priority: 3
version: 2
labels:
  - toc
dependencies: []
parent_id: is-01m7wysdnvzch4gb5zvqwvn04e
created_at: 2026-11-18T00:57:29.509Z
updated_at: 2026-11-20T17:14:20.021Z
---
Review A6 on jlevy/metabrowser#517.

No built-in browser caller sets the Markdown mount's includeToc option any more: the folder Overview's README panel stopped passing includeToc: "off" in #517. The option runs mountRendered (builtin_plugins/markdown/rendered.js) -> mb.fetchKpressRender (static/plugin-sdk.js, the toc query parameter) -> the render route, and tests/test_markdown_plugin_ownership.py pins the path.

window.metabrowser and builtin mounts are internal contracts (AGENTS.md, "Compatibility and Legacy Code"), so an option with no caller is removable: drop includeToc from mountRendered's options and types.d.ts, and from fetchKpressRender if nothing else sets it, with the test line. Keep the route's toc query and the Python include_toc callers (the GitHub plugin's pull_markdown.py and pull_snapshot.py, kpress_adapter.py) if they still use it; check the --api goldens.
