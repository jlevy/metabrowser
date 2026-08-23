# Plugin Authoring

A Metabrowser plugin is a directory with a `manifest.toml` and an `index.js`. The
manifest declares file kinds, preview views, optional assets, and optional Python data
hooks. The JavaScript entry point registers renderers with the browser SDK.

## Trust Model and Discovery

Metabrowser discovers plugins in this order:

1. built-ins shipped in `src/metabrowser/builtin_plugins/`;
2. installed Python entry points in the `metabrowser.plugins` group;
3. directories explicitly supplied with `--plugins-dir` or `METABROWSER_PLUGINS_DIRS`.

Later plugins win plugin-name collisions.
Kind classifiers use explicit priorities and stable discovery order as a tiebreaker.
Configured directories expand `~`, resolve to canonical paths, must exist, and are
deduplicated after environment entries are ordered before command-line entries.

The served root and a user’s home directory are not automatic plugin sources.
This is a security boundary: browsing data must not cause its JavaScript to execute in
the Metabrowser page.

Operator-supplied directory plugins are JavaScript-only.
Python data hooks are accepted from installed entry-point packages, whose modules
already belong to the active Python environment.
When Metabrowser runs through uvx or as a uv tool, install the plugin distribution into
that same isolated environment with uv’s `--with` option.

Inspect discovery without starting the server:

```shell
metab --plugins
metab --plugins --json
metab --plugin markdown
metab --plugin markdown --json
metab --doctor
metab --doctor --json
metab --doctor --plugins-dir ./examples
```

`--doctor` validates manifests, `index.js` files, installed-plugin data-hook imports,
operator-directory JavaScript-only boundaries, and high-priority kind conflicts.
It exits nonzero when any problem is found.
All three modes support `--json` for machine-readable output.
Discovery errors preserve any plugins that loaded successfully but make the command exit
nonzero, so scripts cannot mistake a partial registry for a complete one.
Human-readable data goes to standard output, while human-readable errors go to standard
error.

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
sdk_version = "0.4"

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
metab ./examples --plugins-dir ./examples
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
| `sdk_version` | no | Strongly recommended. Omission means the original SDK `0.1`, not the host’s current version. The resolved value must equal `PLUGIN_SDK_VERSION`. |
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
Specialized binary stores belong in installed plugins so their native readers and value
decoders do not become mandatory Metabrowser dependencies.

Content-based classification is deliberately bounded.
JSON predicates parse only a complete document of at most 256 KiB; YAML predicates
inspect at most the first 16 KiB. An oversized or truncated document does not match that
content predicate, so use `basename`, `ext`, or `path_glob` when large files must be
claimed without reading their contents.

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

- resolve user paths through Metabrowser’s safe-path helpers;
- bound reads and parsing work;
- return useful validation errors without exposing local absolute paths;
- avoid blocking the event loop with synchronous filesystem work;
- keep domain imports inside the plugin package.

A synchronous `def` handler already runs off the event loop: the dispatcher sends it
through Starlette’s threadpool, the same way Starlette offloads its own sync endpoints.
Reach for `async def` only when the handler awaits something.

A hook may serve a large resource in bounded pieces rather than refusing it.
The built-in binary plugin’s `chunk` route is the worked example: it reads a bounded
window of a file’s logical bytes, reports `next_offset`, `has_more`, and the ceiling
that applied, and carries a fingerprint so its view can tell a continued read from a
changed file. See
[Bounded binary byte preview](project/specs/active/plan-2026-08-11-binary-byte-preview.md)
for the size policy and the reasoning behind the compressed-artifact bound.

Explain a refusal in the response body, not only in the status code.
`fetchPluginData` rejects with an `Error` carrying `status` and the parsed `payload`, so
a view can turn `413` plus a `max_preview_bytes` field into a state naming the exact
cutoff instead of hard-coding the limit in JavaScript.

## Browser SDK

The supported API is available as `window.metabrowser`.

### Registration and Lifecycle

```javascript
mb.registerView(kind, viewId, {
  render(container, ctx) {
    // Own the contents of container.
    return {
      dispose() {
        // Abort this mount's requests and release retained resources.
      },
    };
  },
  dispose(container) {
    // Abort requests, remove global listeners, and destroy retained resources.
  },
});
```

`render` runs when the view is first mounted.
Nondefault tabs mount lazily.
`dispose` runs when the preview pane is replaced by another file, an error, or a reload.
It does not run for an ordinary tab switch.
The shell passes the same `container` that was supplied to `render`, so shared renderers
can keep state per mounted view instead of using one module-wide slot.
`render` may return an instance handle with an idempotent `dispose()` method, directly
or through a promise.
Prefer that form when one renderer can have multiple mounts.

The context contains the served-root-relative `path`, selected `kind`, logical `ext`,
size, frontmatter, body text where applicable, and the raw `/api/file` envelope.

Use `mb.getRegisteredView` and `mb.listViewsForKind` for diagnostics.
Do not inspect the registry’s private storage.

### Rendering and Formatting

Useful helpers include:

- `render(template, data)` for auto-escaped Mustache templates;
- `escapeHtml(value)` for carefully constructed HTML strings;
- `wrapWithCopy(html)` for a standard copy-button frame;
- `formatSize`, `formatInteger`, `formatFileCount`, `formatTimestamp`, and `sizeHtml`;
- `countClass(value)` and `sizeClass(value)` for the same magnitude-driven emphasis
  classes used by core numeric readouts;
- `fileTypeClass(pathOrName)` for the shared `ft-*` subtype and
  `fileTypeIcon(pathOrName)` for its host-owned SVG plus `className`;
- `fileTypes` for the immutable semantic type catalog.
  `schema`, `schemaVersion`, `revision`, `fingerprint`, `maxExtensionComponents`, and
  `registryIdentity` identify the loaded File Rollup Format type definitions; ordered
  `groups`, `families`, and `kinds` expose their immutable descriptors.
  `classify(name, ext)` returns registry identities and evidence for one file.
  `matchExtension(ext)` returns the matching family and canonical suffix,
  `canonicalExtension(ext)` preserves unknown extensions, `groupForFile(name, ext)`
  includes whole-filename evidence, and `distributionKeyForExtension(ext)` returns the
  shared family or raw palette key.
  Compare a file rollup’s `registry` identity before combining it with labels or colors
  from this projection;
- `icons` and `icons.withClass`;
- `filterControls` for the host’s accessible filter chips and menus;
- `chart(container, type, data, options)`;
- `ensureAsset(name)`;
- `perf.measure` and `perf.measureAsync`.

`ensureAsset(name)` loads a vendored library that the shell does not put on every page,
and resolves once its globals are present.
Await it before touching the library: a loaded bundle resolves immediately, simultaneous
callers share one load, and it rejects for an unknown name or a script that fails, so a
view can say so instead of rendering into a surface that will not work.
The bundles the host publishes are named in `server.py`; `"chart"` is Chart.js with its
annotation plugin and date adapter.
See [Asset Loading Tiers](development.md#asset-loading-tiers) for which tier an asset
belongs in.

`chart(container, type, data, options)` requires that bundle:
`await metabrowser.ensureAsset("chart")` first, or the call throws.
Chart color fields may use host design-token references such as
`var(--chart-series-info)`. The SDK resolves them for the current palette and updates
the chart when the resolved theme changes.
Retain the returned instance and call `destroy()` from the view’s `dispose` handler to
release both Chart.js resources and the theme subscription.

Avoid inline event-handler strings when possible.
Build DOM elements, attach listeners, and keep cleanup handles in the renderer closure.
When a view displays a file or exact extension, place the result of `fileTypeIcon()` in
the shared `.file-identity-icon` alignment box and mark it decorative.
The returned SVG is trusted host chrome; never pass user-provided markup through this
path.

### Data and Navigation

- `fetchPluginData(plugin, route, params, options?)` calls a declared data hook.
  Pass `{ signal }` so a disposed view aborts its request.
  A non-ok response rejects with an `Error` carrying `status` and the parsed `payload`,
  so a hook’s structured refusal stays readable by its caller.
- `fetchJsonl(path, options)` requests a normalized JSONL envelope.
- `fetchCompleteText(ctx, options)` retrieves a bounded complete source after an initial
  text envelope reports truncation.
- `fetchText(target, options)` retrieves bounded complete source for a canonical
  navigation target and forwards an optional abort signal.
- `fetchKpressRender(ctx, view, options)` requests a KPress-rendered view.
- `loadKpressAssets()` loads the KPress browser assets once.
- `renderTextTruncationWarning(data)` preserves visible truncation warnings.
- `navigation.href(target)` returns the canonical `/view/` URL for a
  `{ path, query?, fragment? }` target.
  Paths are served-root-relative, use `/` separators, and have no leading slash; the
  empty path selects the served root.
- `navigation.open(target, options?)` performs normal user navigation and returns a
  promise. Pass `{ viewId }` to prefer a view declared by the destination; the shell uses
  the destination’s default when that view is unavailable.
  The preference is transient and does not change the target URL.
- `navigation.current()` returns the current target or `null` on the landing URL.
- `fileCatalog.snapshot()` returns an immutable, completion-aware view of files already
  known to the shell.
- `fileCatalog.subscribe(listener)` invalidates inventory-derived plugin results and
  returns an unsubscribe function that the view must call from its disposer.
- `repository` is either `null` or frozen public-safe GitHub identity for the served
  tree: host, owner, repository name, exact revision, current branch, and served
  subdirectory prefix.
  It never contains a local filesystem path.

Use `navigation.href()` for real anchor `href` values so browser status previews,
copy-link, modifier clicks, new tabs, and reloads retain native behavior.
An unmodified in-app activation may then call `navigation.open()`:

```javascript
const target = { path: "docs/guide.md", fragment: "setup" };
const link = document.createElement("a");
link.href = mb.navigation.href(target);
link.textContent = "Setup guide";
link.addEventListener("click", (event) => {
  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
    return;
  }
  event.preventDefault();
  void mb.navigation.open(target);
});
```

Folder aggregate views can use these bounded inventory helpers:

- `fetchRollup(path, options)` reads the in-memory subtree rollup.
  `depth`, `top`, `ext_top`, `filename_top`, `remaining_top`, and `ext_rank` map to
  `/api/rollup`; use `depth: 0`, `top: 0`, and `ext_rank: "dual"` for a tally-only
  count-and-byte summary.
  Both file-type child limits default to 20 and cannot exceed 20.
- `watchRollup(path, options, onUpdate)` performs the initial fetch and refreshes after
  relevant inventory changes.
  Supply `active` to gate hidden views and `onError` for a local failure state.
  Always call the returned handle’s `dispose()`; when `stale()` is true after
  activation, call `refresh()`.
- Each `ext_tallies` row is
  `[extension, all_files, all_bytes, unignored_files, unignored_bytes]`. The empty
  extension is the aggregate **Other** tail; `(none)` is the distinct extensionless
  category.
- `file_type_breakdown` is the native File Rollup Format result.
  It carries matching registry identity, exact `all` and `unignored` populations,
  ordered nonempty group and family rows, complete canonical-extension children, and
  bounded No extension and `remaining_types` children with exact Others remainders; the
  latter is presented as **Other types** in the built-in UI.

### Folder Overview Contributions

The built-in folder plugin publishes `mb.folderOverview` before installed plugins load.
Use it when a capability summarizes a folder inside **Overview**. A primary working mode
such as a future Files listing remains a normal `registerView("folder", ...)` tab.

```javascript
const unregister = mb.folderOverview.registerPanel("hello.license", {
  label: "License",
  placement: "supplemental",
  presentation: "surface",
  printable: false,
  async resolve(ctx, { signal }) {
    const url = new URL("/api/plugin/hello/license", window.location.origin);
    url.searchParams.set("path", ctx.path);
    const response = await fetch(url, { signal });
    if (!response.ok) {
      throw new mb.errors.RequestError("Could not load the license summary.", {
        operation: "helloLicense",
        status: response.status,
      });
    }
    const data = await response.json();
    return data.present ? { key: data.path, data } : null;
  },
  mount(container, _ctx, data, { signal }) {
    container.textContent = data.summary;
    return {
      dispose() {
        // Remove listeners and cancel work owned by this mount.
      },
    };
  },
});
```

Panel IDs must be plugin-qualified.
`placement` is `summary`, `content`, or `supplemental`; fixed placement order and then
the panel ID determine layout.
`presentation` is `surface` for a flat host-rendered panel body or `document` when the
renderer owns its normal document surface.
The Overview composer supplies the same visible section heading and responsive
Markdown-text alignment for both presentations; panel mounts must not repeat that
heading or add an Overview-level disclosure.
Set `required: true` only when returning null is a contract error.
A resolver returns `{key, data}` or null; matching keys preserve a mounted panel and
call its optional `update(ctx, data)` method.
Resolvers and mounts receive abort signals, one failure remains local to its panel, and
every returned disposer must be idempotent.
`listPanels()` returns the frozen deterministic descriptor list.

The surrounding folder envelope is available through
`mb.folderContext.subscribe(path, onUpdate)`. The shell seeds and multiplexes that
context, so subscribers do not start parallel `/api/file` refreshes.
Unsubscribe on disposal.
`mb.viewState.isActive(container)` and `subscribeActive(container, listener)` let a lazy
view defer hidden work.
A composite renderer calls `mb.setViewPrintState(container, state)` when its effective
printability changes.

The Markdown built-in exposes
`mb.builtins.markdown.mountRendered(container, ctx, {signal})` for a document panel.
It uses the ordinary KPress Markdown presentation and returns an instance-specific
handle that aborts its request and disposes its own table of contents, enhanced-link
listeners, pending fragment work, and any nested Obsidian transclusions.
Note, heading, and named-block transclusions share depth, document, source-byte,
elapsed-time, cycle, abort, and disposal limits across the mounted document.
`mb.builtins.markdown.analyzeGraph({signal, limits})` returns a bounded immutable
snapshot of Markdown nodes, resolved edges, unresolved destinations, backlinks,
diagnostics, aggregate source bytes, and an explicit completeness flag.
It performs no live catalog subscription and does not provide visualization.
Do not copy Markdown DOM or TOC behavior into a folder contribution.

Use only the SDK surface documented here and in `static/plugin-sdk.js`. Variables in
`app.js` are implementation details and may change without a plugin compatibility
guarantee.

The SDK is versioned with the release, not independently, and the version is enforced
rather than advisory.
`PLUGIN_SDK_VERSION` in `plugin_loader/manifest.py` is the contract this host provides.
A manifest should declare `sdk_version`. A manifest that omits it targets the original
SDK `0.1` and nothing later, so omission never silently follows the host forward onto a
contract the plugin was not written against; once the host moves past `0.1`, an omitted
value is refused like any other stale one.
A different resolved value is refused when it loads, with a message naming the required
version, and `metab --doctor` reports the same problem before it reaches a user.
There is no negotiation and no shim for an older surface.

That gate is deliberately strict because the alternative is worse.
A method that moves or changes shape does so in one commit across core and every
built-in plugin; the constant is bumped only when the contract actually breaks, and the
break is recorded in `CHANGELOG.md`. An external plugin updates against the release it
targets and sets its `sdk_version` to match.
A young plugin ecosystem is cheaper to upgrade than to carry.
See [Compatibility and Legacy Code](development.md#compatibility-and-legacy-code).

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

### Python Sidekick API

Import server-integrated helpers from `metabrowser`, not private package modules:

```python
from metabrowser import (
    ArtifactCompressionError,
    ArtifactPath,
    JsonlParseLimitError,
    relativize_path,
    resolve_directory,
    resolve_path,
)
```

- `resolve_path(value)` resolves a served-root-relative path and rejects traversal.
  An empty string returns the served root, and any successful result may be a file or
  directory.
- `resolve_directory(value)` applies the same containment rule and requires a directory.
- `relativize_path(value)` converts an absolute path under the served root to a client
  path.
- `ArtifactPath` reads supported single-file compression formats transparently and with
  decompression limits.
- `register_root_callback(callback)` invalidates plugin caches when the served root
  changes.
- `LogEvent`, `LogParser`, `detect_adapter(lines)`, and
  `register_log_adapter(name, detector, parser_factory)` define the JSONL adapter
  contract described above.
- `extract_agent_charts_cached(path)` reuses the generic agent-log chart projection and
  returns `None` if the file is absent.
- `ArtifactCompressionError`, `ArtifactDecompressionLimitError`, and
  `ArtifactDecompressionTimeoutError` let sidekicks distinguish malformed compressed
  data from resource-limit and CPU-time failures.
  `ArtifactPath` and chart extraction can raise them.
- `JsonlParseLimitError` is raised when chart extraction exceeds the JSONL parser’s
  decompressed-input limit.

These helpers share the server’s active root and lifecycle.
Do not cache the resolved root or import underscored helpers from
`metabrowser.paths_safe`. The sidekick surface is provisional during the 0.x series;
release notes will identify changes before 1.0. `metabrowser.plugin_api.__all__`
contains the sidekick names above, and `metabrowser.__all__` adds `CLIError` and
`__version__`. CLI integrations can catch `CLIError` to preserve the command’s
user-facing message and exit code.
Plugin-loader and manifest implementation types remain available from their defining
modules but are not part of this compatibility contract.

Ensure the wheel includes the manifest, JavaScript, CSS, and any extra assets.
Test the built wheel in an isolated environment; an editable source checkout can conceal
missing package data.

## Testing Checklist

Before publishing a plugin:

1. Run `metab --doctor` in a clean environment.
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
