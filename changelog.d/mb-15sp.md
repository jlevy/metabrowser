- **Breaking (Plugin SDK):** `PLUGIN_SDK_VERSION` is now `0.8`. A plugin shares helpers
  by exporting them from its `index.js` module, and a plugin that uses another’s names
  it in its manifest, `[plugin] requires = ["markdown"]`, and gets its exports with
  `await metabrowser.plugins.load("markdown")`, which loads the provider on demand
  ([Declared Dependencies](docs/plugins.md#declared-dependencies)).
  `metabrowser.builtins` and the render-time-only rule for reading it are gone: the
  Markdown plugin’s `mountRendered`, `renderSource`, and `drawDiagrams`, and the
  structured plugin’s `renderInlineTree` and tree helpers, are their modules’ exports.
  Update a plugin’s reads and set its `sdk_version` to `0.8`.

- Discovery refuses a plugin that requires one that was not discovered or was refused,
  and every plugin on a cycle of requirements, naming the cause.
  `metab --doctor` lists each refusal and reports the plugin dependency graph, and
  `metab --plugins` and `--plugin NAME` show each plugin’s `requires`.

- An agent log’s opened event payload is always drawn as the structured tree, which
  loads with the first payload opened; before, it was a flat JSON block unless a JSON or
  YAML file had been opened first.
