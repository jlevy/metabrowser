---
type: is
id: is-01kxz2zv6jz6e5w02acj1xb44d
title: "P1: built-in folder plugin with README view"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies:
  - type: blocks
    target: is-01kxz3131cqxh1xc4zdq4x9ss8
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-20T06:21:37.874Z
updated_at: 2026-07-20T06:22:31.716Z
---
New src/metabrowser/builtin_plugins/folder/: manifest.toml ([plugin] name=folder, extra_scripts=[treemap_layout.js]; [[view]] treemap default + readme kpress; no [[kind]] rules), index.js registering readme view via mb.builtins.markdown against raw.readme_path with explicit empty state; treemap view registers as placeholder until P3 renderer lands (loading state per design system). Node vm tests tests/test_folder_plugin_behavior_js.py (pattern: test_agent_log_plugin_behavior_js.py). See spec 'Built-in Folder Plugin'.
