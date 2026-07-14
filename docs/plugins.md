# Plugin Authoring

A MetaBrowser plugin is a directory with a `manifest.toml` and an `index.js`. The
manifest declares file kinds, preview views, optional assets, and optional Python data
hooks. The JavaScript entry point registers renderers with the browser SDK.

## Trust Model and Discovery

MetaBrowser discovers plugins in this order:

1. built-ins shipped in `src/metabrowser/builtin_plugins/`;
2. installed Python entry points in the `metabrowser.plugins` group;
3. directories explicitly supplied with `--plugins-dir` or `METABROWSER_PLUGINS_DIRS`.

Later plugins win plugin-name collisions.
Kind classifiers use explicit priorities and stable discovery order as a tiebreaker.

The served root and a user’s home directory are not automatic plugin sources.
This is a security boundary: browsing data must not cause its JavaScript to execute in
the MetaBrowser page.

Operator-supplied directory plugins are JavaScript-only.
Python data hooks are accepted from installed entry-point packages, whose modules
already belong to the active Python environment.

Inspect discovery without starting the server:

```shell
metabrowser plugins list
metabrowser plugins list --json
metabrowser plugins show markdown
metabrowser plugins doctor
metabrowser plugins doctor --plugins-dir ./examples
```

`doctor` validates manifests, `index.js` files, installed-plugin data-hook imports,
operator-directory JavaScript-only boundaries, and high-priority kind conflicts.
It exits nonzero when any problem is found.

## Minimal Plugin

Create this structure:

```text
examples/
└── hello/
    ├── index.js
    └── manifest.toml
```

`manifest.toml`:

```toml
[plugin]
name = "hello"
display_name = "Hello"
version = "0.1.0"

[[kind]]
id = "hello-document"
match = { ext = ".md", frontmatter_has_key = "hello" }
priority = 100

[[view]]
kind = "hello-document"
id = "card"
label = "Hello"
default = true
```

`index.js`:

```javascript
(function () {
  const mb = window.metabrowser;

  mb.registerView("hello-document", "card", {
    render(container, ctx) {
      container.innerHTML = mb.render(
        '<section class="mb-plugin-hello">Hello, {{frontmatter.hello}}!</section>',
        ctx,
      );
    },
  });
})();
```

Run it explicitly:

```shell
metabrowser serve ./examples --plugins-dir ./examples
```

Plugin discovery happens at startup, so restart the server after changing a manifest or
entry point.

## Manifest

### Plugin Metadata

The `[plugin]` table supports:

| Key | Required | Meaning |
| --- | --- | --- |
| `name` | yes | Stable lowercase URL and registry identifier. |
| `display_name` | no | Human-readable diagnostics label. |
| `version` | no | Plugin version string. |
| `sdk_version` | no | Browser SDK contract version; defaults to `"0.1"`. |
| `extra_scripts` | no | Plain JavaScript filenames loaded before `index.js`. |
| `extra_styles` | no | Plain CSS filenames loaded with the page. |

Extra asset entries may not contain slashes, traversal segments, or a leading dot.

### Kind Rules

Each `[[kind]]` declares a stable `id`, a `match` table, and an optional `priority`.
Multiple rules may share an ID; they act as alternatives for the same kind.

Supported match fields include:

| Field | Meaning |
| --- | --- |
| `ext` | One logical extension, including its leading dot. |
| `exts` | A list of alternative logical extensions. |
| `basename` | Exact filename. |
| `adapter` | Adapter identified while sniffing a JSONL stream. |
| `frontmatter_has_key` | Required top-level Markdown frontmatter key. |
| `frontmatter_schema_prefix` | Prefix required in the frontmatter `schema` value. |
| `json_has_key` | Required top-level JSON object key. |
| `json_value_prefix` | Prefix required in the selected JSON value. |
| `yaml_has_key` | Required top-level YAML mapping key. |
| `yaml_value_prefix` | Prefix required in the selected YAML value. |
| `folder_marker` | Exact marker filename that also decorates its parent directory. |
| `path_glob` | Gitignore-style pattern for the served-root-relative path. |

Fields within one rule combine with AND. Rules with the same kind ID combine with OR. At
least one match field is required.
Built-ins normally use priority `0`; a specialized plugin can use a higher priority to
claim a narrower format.

Classification reads only bounded prefixes when it needs structured metadata.
Do not design a classifier that requires loading an entire large artifact.

### Views

Each `[[view]]` binds a tab to a kind:

```toml
[[view]]
kind = "hello-document"
id = "source"
label = "Source"
container_class = "content-body metabrowser-source-host"
printable = true
print_profile = "source"
render_runtime = "client"
```

View order in the manifest is tab order.
At most one view per kind may set `default = true`. A plugin may register a view for a
kind declared by another plugin, which is useful for composing generic renderers.

`render_runtime` documents whether the view is rendered by the client or by KPress.
Printable views should also declare a `print_profile` appropriate to documents or source
code.

### Python Data Hooks

Installed entry-point plugins may declare HTTP data hooks:

```toml
[[data_hook]]
route = "summary"
sidekick = "example_plugin.sidekick:summary_handler"
```

The handler receives a Starlette `Request` and may return a response or JSON-compatible
data according to the route adapter.
Each `route` must be a unique single path segment within its plugin manifest.
The route is mounted at:

```text
/api/plugin/<plugin-name>/<route>
```

Keep handlers defensive:

- resolve user paths through MetaBrowser’s safe-path helpers;
- bound reads and parsing work;
- return useful validation errors without exposing local absolute paths;
- avoid blocking the event loop with synchronous filesystem work;
- keep domain imports inside the plugin package.

## Browser SDK

The supported API is available as `window.metabrowser`.

### Registration and Lifecycle

```javascript
mb.registerView(kind, viewId, {
  async render(container, ctx) {
    // Own the contents of container.
  },
  dispose() {
    // Abort requests, remove global listeners, and destroy retained resources.
  },
});
```

`render` runs when the view is first mounted.
Nondefault tabs mount lazily.
`dispose` runs when the preview pane is replaced by another file, an error, or a reload.
It does not run for an ordinary tab switch.

The context contains the served-root-relative `path`, selected `kind`, logical `ext`,
size, frontmatter, body text where applicable, and the raw `/api/file` envelope.

Use `mb.getRegisteredView` and `mb.listViewsForKind` for diagnostics.
Do not inspect the registry’s private storage.

### Rendering and Formatting

Useful helpers include:

- `render(template, data)` for auto-escaped Mustache templates;
- `escapeHtml(value)` for carefully constructed HTML strings;
- `wrapWithCopy(html)` for a standard copy-button frame;
- `formatSize`, `formatTimestamp`, and `sizeHtml`;
- `icons` and `icons.withClass`;
- `chart(container, type, data, options)`;
- `perf.measure` and `perf.measureAsync`.

Avoid inline event-handler strings when possible.
Build DOM elements, attach listeners, and keep cleanup handles in the renderer closure.

### Data and Navigation

- `fetchPluginData(plugin, route, params)` calls a declared data hook.
- `fetchJsonl(path, options)` requests a normalized JSONL envelope.
- `fetchKpressRender(ctx, view, options)` requests a KPress-rendered view.
- `loadKpressAssets()` loads the KPress browser assets once.
- `renderTextTruncationWarning(data)` preserves visible truncation warnings.
- `openPath(path)` asks the shell to navigate without reaching into private `app.js`
  functions.

Use only the SDK surface documented here and in `static/plugin_sdk.js`. Variables in
`app.js` are implementation details and may change without a plugin compatibility
guarantee.

## Packaging a Python Plugin

Return the directory containing `manifest.toml` from an importable function:

```python
from pathlib import Path


def plugin_dir() -> Path:
    return Path(__file__).with_name("plugin")
```

Register it in `pyproject.toml`:

```toml
[project.entry-points."metabrowser.plugins"]
example = "example_plugin:plugin_dir"
```

### Plugin-Owned JSONL Adapters

Plugins that recognize an additional JSONL event format can register a detector and
parser factory when their entry-point module loads:

```python
from typing import Any

from metabrowser import LogEvent, register_log_adapter


class ExampleParser:
    adapter_name = "example"

    def parse_line(self, line: str) -> list[LogEvent]:
        return [LogEvent(kind="system", summary=line, adapter=self.adapter_name)]

    def flush(self) -> list[LogEvent]:
        return []


def is_example_event(event: dict[str, Any]) -> bool:
    return event.get("format") == "example"


register_log_adapter(
    "example",
    detector=is_example_event,
    parser_factory=ExampleParser,
)
```

The detector receives parsed objects from the beginning of the stream.
Registering the same detector and factory more than once is idempotent, while a second
plugin attempting to claim an existing adapter name raises an error.
A detector failure is logged and skipped so one third-party adapter cannot break
detection for every JSONL file.
Keep it fast, deterministic, and free of filesystem or network work.
The factory must return a fresh parser for each file or live stream.
Built-in adapter names cannot be replaced.

Ensure the wheel includes the manifest, JavaScript, CSS, and any extra assets.
Test the built wheel in an isolated environment; an editable source checkout can conceal
missing package data.

## Testing Checklist

Before publishing a plugin:

1. Run `metabrowser plugins doctor` in a clean environment.
2. Confirm every manifest view has a matching `registerView` call.
3. Exercise default and lazy-mounted tabs.
4. Verify `dispose` stops listeners, streams, timers, and chart instances.
5. Test path validation and malformed data-hook inputs.
6. Build the wheel and confirm all static assets are present.
7. Browse data with the plugin absent to verify core fallbacks remain usable.

See [end-to-end testing](e2e-testing.md) for the repository’s browser-side contract
tests.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
