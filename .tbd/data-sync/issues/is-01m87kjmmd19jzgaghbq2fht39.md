---
type: is
id: is-01m87kjmmd19jzgaghbq2fht39
title: Plugins declare their Python packages; a check keeps the declarations true
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-24-pdf-plugin-and-open-in-default-app.md
labels: []
dependencies: []
parent_id: is-01m87bky1pb8rhr10p26bsp6w6
created_at: 2026-11-24T20:22:24.616Z
updated_at: 2026-11-24T20:22:24.616Z
---
Manifest field python_requires listing every third-party distribution a plugin imports. A lint-check check: every third-party import under builtin_plugins/<name>/ is declared by that plugin; every declared package is in pyproject dependencies; core code imports no plugin-only package; a runtime dependency nothing imports fails (move psutil, used only by devtools, to a dev group). metab --plugins shows each plugin's packages, plugin-only marked, pinned in cli-plugins.tryscript.md.
