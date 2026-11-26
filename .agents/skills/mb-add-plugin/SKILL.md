---
name: mb-add-plugin
description: >-
  Add or change a Metabrowser plugin: a file kind, a view, a data hook, a table source,
  a JSONL log adapter, or a container, as a built-in or an installed plugin. Use when
  someone asks Metabrowser to open, render, preview, or navigate a new kind of file, or
  to extend the browser SDK's views. For a programming language, use mb-add-language.
---
# Add a Plugin to Metabrowser

The documents are the source of truth; read them before writing code:

1. [Plugin Authoring](../../../docs/plugins.md): the manifest, the `window.metabrowser`
   SDK, data hooks, packaging, and the testing checklist.
2. [Adding a File Type](../../../docs/project/architecture/arch-plugin-system.md#adding-a-file-type):
   the steps from an unknown format to a fully supported one.
3. [Adding a Language](../../../docs/adding-a-language.md), through
   [mb-add-language](../mb-add-language/SKILL.md), when the file type is source code.

## Rules That Are Easy to Miss

- A domain format belongs in a plugin, not in core
  ([AGENTS.md](../../../AGENTS.md#browser-and-plugin-boundary)).
  Plugins use only the documented SDK.
- Every new route, kind, and view arrives with its parity row and a golden
  ([CLI and Functional UI Parity](../../../AGENTS.md#cli-and-functional-ui-parity)).
  `metab <dir> --plugins-dir <plugins> --show <file>` shows what the browser will do.
- A renderer returns a disposer, loads large assets on demand, and bounds its work at a
  size it measured ([Rendering Large Content](../../../docs/large-content-rendering.md)).
- Changing the manifest schema or SDK contract means bumping `PLUGIN_SDK_VERSION` and
  every built-in manifest in the same commit.

Finish with `make verify` and a changelog fragment
([changelog.d](../../../changelog.d/README.md)).
