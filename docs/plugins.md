# Plugin Authoring

A Metabrowser plugin is a directory with a `manifest.toml` and an `index.js`. The
manifest declares file kinds, preview views, optional assets, and optional Python data
hooks. The JavaScript entry point registers renderers with the browser SDK. Every
built-in view is a plugin of this shape;
[Plugin System](project/architecture/arch-plugin-system.md) describes how the host loads
them and walks through adding a file type.

## Trust Model and Discovery

Metabrowser discovers plugins in this order:

1. built-ins shipped in `src/metabrowser/builtin_plugins/`;
2. installed Python entry points in the `metabrowser.plugins` group;
3. directories explicitly supplied with `--plugins-dir` or `METABROWSER_PLUGINS_DIRS` in
   the process environment.
   A `.env` file cannot supply that variable: the `.env` chain walks up from the working
   directory, so a repository browsed from inside itself would otherwise become a plugin
   source. [Command Line](command-line.md#environment-variables) lists the variables a
   `.env` file may set.

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

## Inspecting Plugins

Use the plugin modes without starting a server.

```shell
metab --plugins                   # plugins accepted by discovery and any refusals
metab --plugin agents             # resolved manifest for Agent Session Browser
metab --doctor                    # check plugins and the rest of the setup
metab --plugins --json            # inventory and discovery errors for scripts
metab --doctor --plugins-dir ./examples
```

`--doctor` validates manifests, `index.js` files, installed-plugin data-hook imports,
operator-directory JavaScript-only boundaries, view keys, and high-priority kind
conflicts, and checks that the packaged repository-cache record schemas are intact.
After the verdict it reports GitHub CLI’s state, which never changes the exit status
([diagnostics](command-line.md#diagnostics-and-plugins)). All three modes take `--json`,
write data to standard output and errors to standard error, and exit nonzero on any
problem, including a discovery error beside plugins that loaded, so a script cannot
mistake a partial registry for a complete one.

The Mac app shows the same discovery inventory for its selected runtime under **Settings
→ Plugins**. This is what a new app server discovers.
Browser renderers load as their views are needed.
See [Mac app settings](macos-app.md#settings).

## Built-in Agent Support

**Agent Session Browser** is the built-in plugin with the ID `agents`. It owns Claude
Code and Codex home detection, log adapters, session readers, the catalog, and the
browsing views. Each reader interprets its provider’s on-disk formats and passes
normalized session records and events to the shared views.
The host supplies the plugin loader, scoped file access, and a generic JSONL parser
registry. The same registry lets installed plugins register their own
[JSONL adapters](#plugin-owned-jsonl-adapters).

The manifest’s `requires = ["structured"]` declares the plugin used to render event
payloads. The Codex provider reads known tables using Python’s SQLite library.
The `sqlite` plugin separately provides general-purpose database browsing and requires
`table`. The bundled `fsqlite` plugin adds store-specific views and requires both
`sqlite` and `table`. `metab --plugins` lists these edges in its `REQUIRES` column.
The Mac app shows them in Settings → Plugins alongside each plugin.

The [agent browsing guide](working-with-agents.md#browsing-agent-history) explains what
Agents reads and how the session lists work.

## Path Identity

The SDK uses the inventory’s escaped relative paths in API requests, browser navigation,
and catalog records.
Keep a received `path` unchanged when passing it to another API. A literal percent sign
in a native filename is `%25` in its identity; for example, `100%.md` has identity
`100%25.md`. On POSIX a backslash in a filename is `%5C`, and undecodable platform bytes
also have lossless escapes.
The browser’s navigation API converts these identities to human-facing `/view/` URLs,
and a sidekick crosses to the filesystem only through the
[Python Sidekick API](#python-sidekick-api), never by joining an API path onto the
served root. The [inventory contract](project/architecture/arch-inventory-provider.md)
specifies the encoding and scope.
`/commit/` comparison paths belong to Git’s separate address space.

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
sdk_version = "X.Y" # this Metabrowser's PLUGIN_SDK_VERSION

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

Set `sdk_version` to the host’s `PLUGIN_SDK_VERSION`, from
`src/metabrowser/plugin_loader/manifest.py`: `metab --plugin markdown` prints it as the
built-in plugin’s `sdk_version`, and `metab --doctor` names it when a plugin declares
another.

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
| `sdk_version` | no | Strongly recommended. It must equal `PLUGIN_SDK_VERSION`; an omitted value targets the original SDK, not the host’s current one, and is refused. |
| `extra_scripts` | no | Plain JavaScript filenames loaded before `index.js`. |
| `extra_styles` | no | Plain CSS filenames loaded before the plugin’s selected-kind renderer mounts. |
| `requires` | no | Names of the plugins whose exports this plugin loads with `mb.plugins.load`, and `table` for a plugin with a `[[table_source]]`; see [Declared Dependencies](#declared-dependencies). |
| `python_requires` | no | The third-party Python distributions the plugin’s Python code imports, by distribution name (`pyyaml`, not `yaml`); see [Python Dependencies](#python-dependencies). |
| `register` | no | A dotted Python module imported once when the plugin is discovered, to register Python-side extensions; see [Python Registration Module](#python-registration-module). |

Extra asset entries may not contain slashes, traversal segments, or a leading dot.

### Plugin Asset Lifecycle

The SDK loads a plugin when the browser first selects any kind declared by its
`[[kind]]` or `[[view]]` entries, when another plugin calls `ensureKindAssets(kind)`, or
when a plugin that requires it calls `mb.plugins.load(name)`. Plugin CSS and module side
effects therefore do not exist on an unrelated page.

For one plugin, the host loads its automatically detected `styles.css` and every
`extra_styles` entry in parallel and waits for them to settle.
It then loads `extra_scripts` sequentially in manifest order and evaluates `index.js`
last, having fetched it beside the stylesheets.
Every documented `window.metabrowser` function, and Mustache, is in place before any of
a plugin’s code runs, so `render(template, data)` stays synchronous even before idle
prefetch. When several plugins declare the same kind, they load in stable discovery
order, so a later plugin wins a duplicate `registerView` key, matching the manifest view
registry.

The shell addresses a plugin’s files as `/plugin-static/<name>/@<stamp>/<file>`, where
the stamp names the contents of the plugin’s directory, and a browser keeps them without
asking until the stamp changes.
Reach your plugin’s other files with relative URLs (`import "./part.js"`,
`new URL("./worker.js", import.meta.url)`, `url(icon.svg)` in CSS), which inherit the
stamp. An absolute `/plugin-static/<name>/<file>` URL is revalidated on every use, and a
module reached both ways is two instances with separate module state, so use one form.
From a stamped module, `../other/x.js` stays inside your own plugin and is not found,
while `../../other/x.js` reaches another plugin at its unstamped address; reach another
plugin through its exports ([Declared Dependencies](#declared-dependencies)) or
`ensureKindAssets` instead, since plugins are not isolated from each other.
A top-level directory whose name has a stamp’s form cannot be addressed.
`src/metabrowser/asset_stamps.py` documents the policy.

### Kind Rules

Each `[[kind]]` declares a stable `id`, a `match` table, and an optional `priority`.
Multiple rules may share an ID; they act as alternatives for the same kind.

| Field | Meaning |
| --- | --- |
| `ext` | One logical extension, including its leading dot. |
| `exts` | A list of alternative logical extensions. |
| `basename` | Exact filename. |
| `adapter` | Adapter identified while sniffing a JSONL stream. |
| `frontmatter_has_key` | Required top-level Markdown frontmatter key, as text. |
| `frontmatter_schema_prefix` | Prefix required in the frontmatter `schema` value. |
| `json_has_key` | Required top-level JSON object key. |
| `json_value_prefix` | Prefix required in the selected JSON value. |
| `yaml_has_key` | Required top-level YAML mapping key, as text. |
| `yaml_value_prefix` | Prefix required in the selected YAML value. |
| `folder_marker` | Exact marker filename that also decorates its parent directory. |
| `path_glob` | Gitignore-style pattern for the served-root-relative path. |
| `magic` | `{offset, hex}`: bytes a binary format holds at an offset, in hexadecimal. |

Fields within one rule combine with AND. Rules with the same kind ID combine with OR. At
least one match field is required, and `ext` and `exts` are exclusive.
Built-ins normally use priority `0`; a specialized plugin can use a higher priority to
claim a narrower format.

Kind rules apply to files Metabrowser reads as text and to JSONL streams.
A file whose extension is an image extension keeps the built-in `image` kind, and one
whose bytes sniff as binary keeps the built-in `binary` kind unless a `magic` rule or a
`binary = true` rule claims it; a plugin can add a view to either instead.

A `magic` rule claims a binary format by the bytes it starts with, whatever the file is
called: every file that would otherwise be `binary` is checked against every magic rule,
so a SQLite database named `History` is SQLite.
It takes only `ext` or `exts` beside it, which decide the tree’s container chevron and
do not narrow the match for a binary file, and its bytes must end within the sniff
prefix (`MAGIC_MAX_END` in `src/metabrowser/plugin_loader/manifest.py`). It is checked
on the bytes on disk, so a compressed file keeps its kind.
A file with one of those extensions that sniffs as text is claimed too, but only when
its leading bytes hold the magic: an ASCII PDF named `.pdf` is a PDF, and a text file
named `.pdf` is text.
A magic rule with no extension never claims a text file.

```toml
[[kind]]
id = "sqlite"
match = { magic = { offset = 0, hex = "53514c69746520666f726d6174203300" }, exts = [".db"] }
```

A rule with `binary = true` is asked about a served file found to be binary that no
magic rule claimed, and claims it by path, so a compressed format Metabrowser cannot
read reaches the plugin’s views.
It may use only `ext`, `exts`, `basename`, `folder_marker`, and `path_glob`, cannot be a
container, and never matches a text file or a Git blob.
A format whose reader needs a native library belongs in an installed plugin, so the
dependency is never Metabrowser’s.

Content predicates are bounded: JSON predicates parse only a complete document within
`_JSON_CLASSIFICATION_MAX_BYTES`, and YAML predicates a prefix of `_YAML_PREFIX_BYTES`,
both in `src/metabrowser/plugin_loader/classify.py`. An oversized or truncated document
does not match, so claim large files by `basename`, `ext`, or `path_glob`.

Front matter and YAML are read by one bounded loader,
`src/metabrowser/frontmatter_yaml.py`, as YAML 1.2:

- A key that is not a string is matched by its JSON text, the spelling a renderer
  receives: `frontmatter_has_key = "1"` and `yaml_has_key = "1"` match a YAML `1:` key,
  `"true"` a `true:` key, and `"on"` an `on:` key.
  Keys are compared by that text, so `1:` and `"1":` are the same key.
- Scalars are typed as YAML 1.2 types them: `on`, `yes`, `no`, `12:30:45`, a plain `=`,
  and a `<<` that is not a merge key are strings, which `yaml_value_prefix` can match,
  and `0o17` and `1e3` are numbers, which it cannot.
- A document that declares another version, such as `%YAML 1.1`, is not read.
- In a YAML prefix a key that appears twice in one mapping, merged into another or not,
  keeps its last value, as most YAML tools do; in front matter it is an error.
- Front matter or YAML the loader refuses does not match: YAML aliases that write out
  past `FRONTMATTER_MAX_EXPANDED_SIZE` in front matter or
  `_YAML_PREFIX_MAX_EXPANDED_SIZE` in a YAML prefix, nesting past `YAML_MAX_DEPTH`
  (counted in the value, through its aliases, as well as in the text), or a tag the
  loader does not read.

On a Git revision, `path_glob` rules never match, since a blob has no served-root path.

### Views

Each `[[view]]` binds a tab to a kind:

```toml
[[view]]
kind = "hello-document"
id = "source"
label = "Source"
key = "s"
container_class = "content-body metabrowser-source-host"
printable = true
print_profile = "source"
render_runtime = "client"
```

View order in the manifest is tab order.
At most one view per kind may set `default = true`. A plugin may register a view for a
kind declared by another plugin, which is useful for composing generic renderers.
`render_runtime` documents what renders the view; it is descriptive only, since the
view’s registration still dispatches.
A printable view declares a `print_profile`. The values each field accepts are its
`Literal` in `ViewSpec`, in `src/metabrowser/plugin_loader/manifest.py`.

A view may set `offer = "module:function"`, a Python predicate that decides where the
view is served; one that raises is logged and its view left out, and an operator
directory’s JavaScript-only plugin cannot declare one.

- **A `folder` view’s predicate** receives the folder’s path.
  The view is served only on folders where it returns true, and an offered view with
  `default = true` is then the folder’s only default, so the page opens on it.
  The predicate runs for every folder page, off the event loop, and should read no more
  than a few directory entries.
  A Git revision’s folders never offer a view.

- **A text kind’s view’s predicate** receives the file’s leading logical bytes, at most
  `CONTENT_PREDICATE_MAX_BYTES` + 1 of them (`plugin_loader/classify.py`), and its
  logical extension, and the view is served only on files where it returns true.
  It runs for every response that lists a text file’s views, the hover prefetch
  included, for a pinned revision’s blobs as for a folder’s files, so it decides from
  those bytes and never parses the whole file.
  Only a file served as text is asked: an image, a binary, a JSONL log, or a container’s
  entry reads no leading bytes for it, so a view of such a kind that declares `offer` is
  never served, and the server logs a warning the first time it leaves one out.
  The structured kind offers its Table view this way, only on a file that starts as a
  list of records (`structured/offer.py`).

`key` is an optional one-letter key for the view’s tab.
A kind with more than one view should give each view one: `v` for a rendered view, `s`
for a source view, and otherwise a letter of the label, as
[Keyboard Shortcuts](design-system.md#keyboard-shortcuts) in the design system sets out.
It is stored and served lowercase, as `views[].key` in the `/api/file` envelope.
The manifest loader refuses a key that is not one ASCII letter, or that the shell
reserves in every kind: the letters in `RESERVED_SHELL_KEYS` in
`src/metabrowser/keymap.py`. When two views of one kind declare the same key, as two
plugins that add views to one kind can, the first view in tab order keeps it, and
`metab --doctor` reports both plugins.
A view that overrides another by id takes its place in tab order.
A key is served only when the kind’s list has two or more views: HTML served without
active content keeps Source alone, and serves it without `S`. `metab --show PATH` prints
each view’s key.

### Python Data Hooks

Installed entry-point plugins may declare HTTP data hooks:

```toml
[[data_hook]]
route = "summary"
sidekick = "example_plugin.sidekick:summary_handler"
methods = ["GET"]
```

The handler receives a Starlette `Request` and may return a response or JSON-compatible
data.
`methods` lists `GET`, `POST`, or both, and defaults to `GET`. Each `route` must be
a unique single path segment within its plugin manifest, mounted at:

```text
/api/plugin/<plugin-name>/<route>
```

Keep handlers defensive:

- resolve user paths through Metabrowser’s safe-path helpers;
- bound reads and parsing work;
- return useful validation errors without exposing local absolute paths;
- avoid blocking the event loop with synchronous filesystem work;
- keep domain imports inside the plugin package.

A synchronous `def` handler already runs off the event loop, in Starlette’s threadpool;
reach for `async def` only when the handler awaits something.
A handler that raises, or returns a status of 500 or more, is logged with its traceback,
and the client receives a `200` response whose JSON has `type: "plugin_error"` and a
`detail`; a view that calls a hook should recognize that shape and show a local failure.

Explain a refusal in the response body, not only in the status code.
`fetchPluginData` rejects with an `Error` carrying `status` and the parsed `payload`, so
a view can turn `413` plus a `max_preview_bytes` field into a state naming the exact
cutoff instead of hard-coding the limit in JavaScript.
A hook may also serve a large resource in bounded pieces: the built-in binary plugin’s
`chunk` route reads a bounded window, reports `next_offset`, `has_more`, and the ceiling
that applied, and carries a fingerprint so its view can tell a continued read from a
changed file
([bounded binary byte preview](project/specs/done/plan-2026-08-11-binary-byte-preview.md)).

#### Reading Content

Metabrowser serves two kinds of source: an attached folder and an immutable Git-revision
pin over a store with no working tree.
A hook that reads bytes uses the content reader for both, and never asks which one is
active:

```python
from metabrowser import (
    ContentReadError,
    read_content_window,
    resolve_content,
)
from starlette.responses import JSONResponse

MAX_BYTES = 256 * 1024  # this hook's own ceiling; say why beside the constant


async def summary_handler(request):
    identity = request.query_params.get("path", "")
    try:
        ref = await resolve_content(identity)
        if ref is None:
            return JSONResponse({"error": "Not found"}, status_code=404)
        if ref.logical_ext != ".log":
            return JSONResponse({"error": "Unsupported extension"}, status_code=400)
        window = await read_content_window(ref, max_bytes=MAX_BYTES)
    except ContentReadError as exc:
        return JSONResponse({"error": str(exc), "code": exc.code}, status_code=exc.http_status)
    return JSONResponse(
        {
            "path": ref.identity,
            "fingerprint": ref.fingerprint,
            "lines": window.data.count(b"\n"),
            "truncated": window.has_more,
        }
    )
```

- Pass back the `path` the client sent.
  It is an inventory identity under a folder and a `GitPath` wire on a pin, opaque to
  the hook either way; `ref.identity` is the canonical spelling to echo.
- `ref.fingerprint` changes exactly when the bytes can have, so it keys a hook’s own
  cache and an `ETag`, whether it is an mtime hash or a blob object id.
- `max_bytes` is required, and it bounds **bytes**, not a decoded string, so decode
  `window.data` afterwards.
  `window.has_more` reports that content continues past the window; it is the only
  trustworthy truncation answer for a compressed artifact, whose declared length lives
  in a trailer nothing verifies until the stream is decoded.
- `ref.stored_size` is the size the source stores, compressed for a compressed artifact,
  and costs no read. It is `None` only for a blob a pin’s store does not hold, which no
  read returns either.
- `stat_content(ref)` returns the validated logical size, which differs from the stored
  size exactly for a compressed artifact.
  It can cost a full decode and can fail, so use it only when the response needs a
  total, as the binary plugin’s scrollbar does.
- `resolve_content_container(identity, suffixes=(".patch",))` resolves a
  `<content>/<inner>` address for a container kind, scoped to the suffixes the hook
  claims, with the server’s own depth bound, `MAX_CONTAINER_INNER_DEPTH`.
  `suffixes=None` claims any name, for a kind matched by its bytes whose hook checks the
  content itself, as the SQLite plugin does.
- Every failure is a `ContentReadError` with a stable `code` and the `http_status`
  Metabrowser’s own routes answer with, so one `except` covers a missing object, an
  oversized blob, an unreadable compressed stream, a timeout, and a subject that cannot
  read content; branch on `code`, not on exception classes.

Reads run off the event loop on both kinds, so an `async def` handler stays responsive
without arranging that itself.

#### Table Sources

A plugin whose files are tables lets the built-in `table` plugin serve them: it claims
the kind, requires `table`, and names a Python adapter for the kind.

```toml
[plugin]
name = "example-tables"
requires = ["table"]

[[kind]]
id = "example-table"
match = { ext = ".extable" }
priority = 100

[[table_source]]
kind = "example-table"
adapter = "example_plugin.tables:adapter"
```

The adapter takes a `TableHandle` and returns an object with the `TableSource` methods:
`generation()`, `tables()`, `schema(table)`, `rows(table, query, budget)`,
`record(table, key, budget)`, and `card(table, key, budget)`. They are synchronous and
run on the route threadpool, and every file of the kind is then served by
`/api/plugin/table/{tables,schema,rows,record,card}?path=` with no route of your own.
`metabrowser.plugin_api` exports the types, the cell and token helpers, and the bounds;
[Table Sources](project/architecture/arch-plugin-system.md#table-sources) describes the
routes, and `builtin_plugins/delimited/source.py` is a complete source.
`builtin_plugins/structured/records.py` is another, a Table view of a kind that has
other views: it reads the plugin’s own parse of a JSON or YAML file and refuses, with
`SourceUnreadableError` and its reason, any document that holds no table.

- A `[[table_source]]` names one of its own plugin’s kinds, once, and its plugin must
  require `table`; an operator-directory plugin’s are ignored, since it runs no Python.
- Read through `handle.read_window(max_bytes=...)`, which answers on a folder and on a
  Git pin alike; `handle.local_path` is the real path on a served folder, or None.
- `generation()` only stats files and reads bounded headers.
  `content_generation(handle)` is the file’s identity, size, and modification time, or a
  pinned blob’s object id.
  Key anything you cache by it.
- A cell is a scalar or one of the envelopes `integer_cell`, `real_cell`, `text_cell`,
  `blob_cell`, and `stored_cell` build, so a large integer keeps its digits, a long
  value says its length, bytes are hex with their size, and a value whose stored type
  differs from its field’s says so.
  A text the source read only in part, whose length in characters it cannot know, is
  `{text, bytes}`, the whole value’s size in bytes; one it could not preview is
  `{length, preview: false}`. A reference is `{ref: {table, key, label}}`, and a value
  naming a record that is not there is
  `{ref: {table, key: null, label, missing: true}}`, drawn as its value marked missing.
- A file of several tables is a navigation container whose children are its tables:
  `<file>/<table>` reaches the source with `table` set to the inner path, so a source’s
  table ids are its address segments, and its kind declares a `children` hook that lists
  them
  ([Navigation Containers](project/architecture/arch-plugin-system.md#navigation-containers)).
  The SQLite source (`builtin_plugins/sqlite/`) is one, and the fsqlite store’s
  (`builtin_plugins/fsqlite/`), whose file is a marker naming the database it reads.
- Name a keyless row by its position with `position_key(n)`, counting from 1, and a
  keyed one with `encode_key(values)`; mint cursors with `encode_cursor`, falling back
  to `positional_cursor` past `TABLE_TOKEN_MAX_CHARS`. Every token is deterministic.
  Put the query’s sort and order in a cursor and refuse one minted for another, and
  check every part of a token before using it: a client can send any text.
- Raise a `TableSourceError` subclass, such as `RecordNotFoundError`, to refuse; the
  route answers its `code` and status.
  A `TableQueryError` refuses a malformed parameter or token with `bad_query`.
- Answer rows in the order the query asked for.
  Stop a scan when `budget.expired()` and answer `complete=False` with the reason
  `budget` and the rows found so far; a sort cannot be returned in part, so a sort the
  budget cannot finish answers no rows, the reason `sort_budget`, and `sort_refused`
  naming the field.
- Carry at most `page_row_limit(query.limit, cells_per_row)` rows in a page, so a page
  of wide rows stays within `TABLE_PAGE_CELLS_MAX` cells, and return that number as the
  page’s `limit`.

The table plugin also draws the table: its exports are
`mountTable(container, {path, renderJson})`, which mounts the table view for the table
at `path` and returns a handle with `ready`, `dispose()`, and `refresh()`. `refresh()`
asks the current question again and draws the new answer in place, keeping the focused
row, the row at the top of the view, and the selection by row key, for a source whose
content changes while it is shown.
`renderJson(element, value)`, optional, draws a JSON value (a `{json}` cell) into a
record’s element and returns a handle with `dispose()`, which the view calls when the
record goes; without it the value is its JSON text.
The structured kind’s Table view passes the structured plugin’s inline tree (in
`builtin_plugins/structured/index.js`). Give your kind a Table view that mounts it:

```toml
[[view]]
kind = "example-table"
id = "table"
label = "Table"
key = "v"
default = true
container_class = "content-body table-view-host"
printable = true
print_profile = "table"
```

```javascript
const tables = mb.plugins.load("table"); // start the load as the plugin is evaluated
mb.registerView("example-table", "table", {
  async render(container, ctx) {
    const { mountTable } = await tables;
    return mountTable(container, { path: ctx.path });
  },
});
```

The view keeps its sort, filters, search, columns, and open record in the address’s
query, in the rows route’s own names (`cols` repeated, one field each), so a link
reproduces it. It takes the table’s id from the schema answer’s `table`, and builds a
reference’s address from it.
It draws what a source answers as the route defines it: a page shorter than asked is
read on from `next_after`, a `sort_budget` page is a notice naming the field rather than
an empty table, and `budget`, `source_truncated`, and `truncated` are notices above the
rows. A `source_unreadable` refusal is the source’s own words in place of the table, so
say there why the file holds no table, as the record lists say a document is not one.
A plugin whose files always open in the Table view starts the load when its own module
is evaluated, as above, so the table plugin’s module is on its way while the shell
prepares the pane; one that shows it only sometimes asks for it in `render`.

## Browser SDK

The supported API is available as `window.metabrowser`. Use only the surface documented
here and in `static/plugin-sdk.js`; variables in `app.js` are implementation details
with no plugin compatibility guarantee.
The object also carries console diagnostics, which
[Browser Shell](project/architecture/arch-browser-shell.md#the-sdk-boundary) describes;
a plugin may use `perf.measure` and `perf.measureAsync` to add bounded, stable operation
labels to the shared profile, and does not depend on the others.

### Registration and Lifecycle

```javascript
mb.registerView(kind, viewId, {
  render(container, ctx) {
    // Own the contents of container.
    return {
      ready: initialRender,
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

`render` runs when the view is first mounted, and nondefault tabs mount lazily.
`dispose` runs when the preview pane is replaced by another file, an error, or a reload,
not on an ordinary tab switch, and receives the same `container`, so a shared renderer
can keep state per mount.
`render` may instead return an instance handle with an idempotent `dispose()`, directly
or through a promise; prefer that form when one renderer can have several mounts.
The handle may expose `ready: Promise<void>` when `render` returns before its first
useful content.
The shell awaits the render promise and `ready` before it shows the view,
and a rejection renders the standard view failure state.
Resolve `ready` once useful content or a handled local error is visible, not after
polling, live updates, or other enhancement that continues while the view is usable.

A handle may expose an idempotent `cancelPending()` that stops requests, timers,
observers, and progressive rendering while leaving its DOM intact.
A retained pull-request page calls it while the next view prepares, and calls
`dispose()` once the content is actually replaced; keep `dispose()` complete and safe
after `cancelPending()`.

The supplied container is connected to the live page, so a renderer may use layout and
observers. During file-to-file navigation it may sit in a transparent, inert stage while
the previous view stays visible
([Staged Handoff](project/architecture/arch-browser-shell.md#staged-handoff)), so scope
DOM access and events to the container, and do not move focus while rendering.
The built-in diff view has one exception: a host that passes `summaryHost` in the render
context, as a commit’s page does for the place under its commit summary, has the diff
draw its Diff summary in that element, outside the container.
The host owns the element, and the diff’s `dispose()` releases the summary’s listeners
and state ([Diff Summary](design-system.md#diff-summary)). A mount that navigation
abandons is disposed even if its readiness never settles.

The context contains the served-root-relative `path`, selected `kind`, logical `ext`,
size, frontmatter, body text where applicable, and the raw `/api/file` envelope.
Use `mb.getRegisteredView` and `mb.listViewsForKind` for diagnostics, not the registry’s
private storage.

### Declared Dependencies

A plugin offers helpers to others by exporting them from its `index.js`, which is an ES
module, as Markdown exports `mountRendered`, `renderSource`, and `drawDiagrams`,
structured data exports `renderInlineTree` and the tree’s helpers, diff exports
`mountFilePatch`, which draws one file’s hunks as Changes does and which GitHub’s Guided
Review draws its excerpts with, and `guidePatchDrawer`, whose
`disclose(section, folded, changed)` makes the bar and chevron that fold a file’s card
in Changes for a card the guide draws itself, its optional `changed` hearing each fold
and opening with whether the card is now open, GitHub exports `pullStateIcon`, which the
shell’s ref selector draws a branch’s pull request with, and PDF exports `mountPdfCard`,
which draws a PDF’s first page, name, and page count where a viewer does not belong, as
a diff’s binary `.pdf` change and a Markdown document’s embedded `.pdf` do.
`mountPdfCard(host, {path | oid, name, links?})` asks the PDF plugin’s
`/api/plugin/pdf/preview` route when the card nears the viewport and shows the image it
names, or the route’s reason when there is none; it never starts a viewer, and its
`dispose()` stops the request and removes the card.
The server draws the image with PDFium in a bounded child process, and for an untrusted
source only inside an operating-system sandbox
([T7](project/architecture/arch-threat-model.md#t7-parsing-browsed-bytes-exhausts-or-takes-over-the-server)).
A plugin that uses them names the provider in its manifest and asks for its exports:

```toml
[plugin]
name = "readme-cards"
requires = ["markdown"]
```

```javascript
const markdown = await mb.plugins.load("markdown");
markdown.mountRendered(container, ctx, { signal });
```

`mb.plugins.load(name)` resolves to the provider’s module namespace once its
stylesheets, extra scripts, and `index.js` have run.
It loads the provider on demand, the first time anything asks for it or selects one of
its kinds, and once: every caller shares that load, so ask for it where you need it,
usually in `render` or a handler, and the cost lands only on pages that use it.
It rejects for a name that is not loaded, and when the provider’s stylesheets, scripts,
or module failed; that failure is the answer to every later call until the page is
reloaded, so a view shows its own error rather than asking again.
The namespace is what `import()` answers, so a provider must not export a function named
`then`: the promise would treat the namespace as a thenable and call it.
A provider whose helpers are costly to fetch can export a function that loads them, so
that its `index.js`, which every page showing one of its kinds loads, stays small: the
agents plugin exports `loadLogRenderers`, which answers its agent-log renderers, and the
diff plugin `mountRenderedFile`, which draws one file of a comparison as the diff view
draws it, rendered layer included, and loads that layer only when it is called; GitHub’s
Guided Review draws a document a step cites whole with it.

Discovery refuses a plugin whose `requires` names a plugin that was not discovered or
was itself refused, and every plugin on a cycle of requirements, since two modules that
each wait for the other’s exports never finish.
An operator plugin that replaces another by name and is refused for its requirements
does not take the name away: like a replacement whose manifest is invalid, it is
reported and the plugin it would have replaced is kept, so a typo in one manifest cannot
refuse the built-ins that require the plugin it shadows.
`metab --doctor` lists each refusal as a problem, causes before the refusals that follow
from them, and reports the graph it kept, and `metab --plugins` and `--plugin NAME` show
each plugin’s `requires`.

Declare every provider you load and load every provider you declare, except `table`,
which a plugin with a `[[table_source]]` requires because the table plugin’s routes
serve it ([Table Sources](#table-sources)). `tests/test_plugin_requirements.py` holds
the built-in plugins to that; nothing checks it for another plugin, because
`mb.plugins.load` cannot tell which plugin called it, so an undeclared load works until
the provider is missing and then fails at render instead of at discovery.
`ensureKindAssets(kind)` and `getRegisteredView(kind, view)` reach a different thing: a
kind’s view, from whichever plugin serves that kind, as the pull-request page draws the
`diff` kind. That needs no declaration, and discovery and the doctor do not see it.
To use one named plugin’s renderers, load its exports, as the generic JSONL and
event-log views draw with the agents plugin’s `renderLog` and `renderRaw`.

### Python Dependencies

`python_requires` names the third-party distributions a plugin’s own Python files
import, whether or not core imports them too.
It installs nothing and pins no version: a built-in plugin ships inside the
`metabrowser` package, so `pyproject.toml` pins every package it imports.
The list says which of Metabrowser’s dependencies a plugin would need if it were moved
out of the package, and which ones core would no longer need.
`devtools/check_plugin_deps.py`, run by `make lint-check`, holds each built-in plugin’s
list to its imports, and every runtime dependency to some import, and prints the
plugin-only packages.
Nothing checks the list for another plugin yet.
`metab --plugins --json` and `--plugin NAME` show each plugin’s list.

### Rendering and Formatting

Useful helpers include:

- `render(template, data)` for auto-escaped Mustache templates, and `escapeHtml(value)`
  for carefully constructed HTML strings;
- `wrapWithCopy(html)` for a standard copy-button frame, and `ownDelegate(element)` with
  `delegateOwnerAttribute()` to stamp a copy control built without it: the shared copy
  listener ignores an unstamped `data-mb-copy`, because a trusted folder’s Markdown can
  write the same markup;
- `decorateExternalLink(anchor, {icon, position})` for the shared external GitHub
  treatment: the GitHub mark, or neutral entity glyphs for an issue or pull-request
  address whose state is unknown; `icon: "github"` and `position: "before"` mark an
  explicit GitHub action.
  Decorate after localization and sanitization;
- `refChipHtml(name, options)` and `refChip(name, options)` for the shared Git ref chip,
  where `name` is the copy value, `label` the display, and `kind` is `local`, `remote`,
  or `tag`; pass `trunk` and `head` only from a Git ref’s `is_trunk` and `is_head`, and
  never restyle the chip ([Branch Chips](design-system.md#branch-chips)). Inside a link
  or button, use `menu: "sibling"` with `mountRefMenus(primary, host)` and call its
  disposer on unmount.
  Pass the full Git ref as `ref` to support browsing its source.
  Use `menu: false` for passive chips;
- `mergeRefs(source, target, options)` for a merge between two branches, the design
  system’s one notation ([Merge Direction](design-system.md#merge-direction));
- `actorIdentity(name, options)` and `actorIdentityHtml(name, options)` for a person: an
  avatar’s box, held from first paint, then the bold name
  ([Actor Identity](design-system.md#actor-identity)). The box holds `avatar`, an https
  address you vouch for, and the host’s person glyph without one or when the image
  fails, so nothing moves.
  The image is requested in anonymous CORS mode with no referrer, so its host must send
  `Access-Control-Allow-Origin`, and a folder served untrusted whose reader has turned
  on Block remote images loads images only from GitHub’s avatar host; any other image
  shows the glyph. `loading` is lazy unless the placement is built again on a repaint;
  `className` and `nameClass` add classes; `placeholder: false` draws no box for a
  person with no avatar, for a dense list row.
  `actorIdentityHtml` writes the same markup, its box holding the glyph;
- `mountCounterpart(corner, page)` and `counterpartButton(counterpart)` for a page’s
  [View on GitHub](design-system.md#view-on-github) button.
  `mountCounterpart` asks the server for the counterpart of `page`, an address as
  `location.pathname` spells it, once per address, and puts the button in `corner`, a
  header’s `.view-header-end`, or leaves it empty.
  A page answered before is drawn at once with its last answer, which a new one replaces
  only when it differs; `prefetchCounterpart(page)` starts the request before the header
  exists, and `mountCounterpart` waits for it.
  `counterpartButton` draws one from the server’s answer, `{provider, label, url}`. Mark
  the corner `data-counterpart` from first paint, so the header leaves it its room, and
  never build a github.com address yourself;
- `renderSourceView(container, data, options)` for the standard bounded, copyable Source
  surface, with truncation controls, the shared language mapping, a line-number gutter,
  and `#L10`-style line anchors; `options.parts`, a list of `{text, language}` that
  joins to the content, shows consecutive code blocks under one gutter, as the Markdown
  Source tab does for front matter;
- `langForExtension(ext)` and `langForPath(pathOrName, ext)` for the language ID backed
  by the host’s vendored grammar registry, or an empty string for plain text, the second
  including names such as `Makefile` and compressed logical names;
- `highlightSyntax(source, language, options)` for bounded DOM-free token runs when a
  renderer, such as a diff, projects tokens itself;
- `formatSize`, `formatInteger`, `formatFileCount`, `formatAge`, `formatTimestamp`, and
  `sizeHtml`; `formatAge(epochSeconds, {style: "relative"})` returns labels such as
  `2h ago`, while its default compact style suits dense navigation, and its label is for
  words, such as an accessible name; `{now}` tells an age as of a time in epoch seconds
  rather than the clock’s;
- `ageLabel(epochSeconds, options)` and `ageLabelHtml(epochSeconds, options)` for an age
  a view shows, the host’s one age builder: a span of its label in its freshness class,
  which alone sets its color, weight, and numerals, after `options.className`, your own
  class, which places it and sets none of those; `options.tip` is its `data-tip-text`,
  and `style` and `now` are `formatAge`’s; an unknown time is an empty span, or “” as
  markup. `retellAge(element, epochSeconds, options)` tells a drawn age again as time
  passes and returns its label ([Age](design-system.md#age));
- `titleNodes(title)` for a commit’s or a pull request’s title, as the nodes its element
  holds: a conventional-commit prefix such as `feat(ledger):` in a `span.title-prefix`,
  which the host draws at regular weight, then the rest, which keeps the element’s
  weight; a title with no prefix is its text alone ([Titles](design-system.md#titles));
- `shortCommit(commit)` for a commit’s ID as every line names one, cut from its full ID
  to the host’s one length; put it in an element of class `git-commit-sha`, which sets
  it in the commit-ID face and gray at the size of the text around it, so give the
  element no size of its own, and keep the full ID for copying and links
  ([Short Commit IDs](design-system.md#short-commit-ids));
- `countPartsNodes(parts)` for a count summary, such as “3 success · 1 failure”, as the
  nodes its element holds, painted as the host paints every count summary: the parts are
  words as strings, `{number}`, drawn bold, `{punctuation}` for a list’s comma and
  `{separator}` for the dot between a line’s groups, both drawn gray, the dot hidden
  from assistive technology with an optional `spoken` said in its place, and
  `{status, letter, count}` for a status count, “21 A”, its number and letter drawn bold
  in the status’s color
  ([Count Summaries Bold Their Numbers](design-system.md#count-summaries-bold-their-numbers));
- `changeLine(change)` and `changeLineNodes(line, options)` for a brief change line, “10
  A, 5 D, 4 M · +1,234 −567”, the host’s one component for a change set’s statuses and
  line totals: `changeLine` builds it from `{statuses, additions, deletions}`, each
  status `{status, letter, word, count}` in the order shown and a count `null` where it
  is not known, in the host’s number format, and returns its parts, its `text`, and its
  `label` in words, a total of zero left out, “+1,234” for a change that only adds
  lines, and a change of none “0 lines”; `changeLineNodes` paints it as the nodes of one
  `span.change-line`, with `{spoken: ", "}` on a line whose name does not say it in
  words ([Brief Change Line](design-system.md#brief-change-line));
- `changeSizeLine(change)` and `changeSizeLineNodes(line)` for a change set’s size line,
  “77 commits · 83 files changed · 2.3 MB compressed (14.0 MB raw diff)”:
  `changeSizeLine` builds it from `{commits?, files, pushedBytes?, diffBytes?}`, a count
  `null` where it is not known and left out where `undefined`, and the size group there
  once `pushedBytes` is known, and returns its parts, `text`, `label`, and the size’s
  `tooltip`; `changeSizeLineNodes` paints it as the nodes of one `span.change-size-line`
  ([Change Size Line](design-system.md#change-size-line));
- `countClass(value)` and `sizeClass(value)` for the magnitude-driven emphasis classes
  of core numeric readouts;
- `fileTypeClass(pathOrName)` for the shared `ft-*` subtype and
  `fileTypeIcon(pathOrName)` for its host-owned SVG plus `className`;
- `fileTypes` for the immutable File Rollup Format type catalog: its identity (`schema`,
  `schemaVersion`, `revision`, `fingerprint`, `registryIdentity`), its ordered `groups`,
  `families`, and `kinds`, and `classify`, `matchExtension`, `canonicalExtension`,
  `groupForFile`, and `distributionKeyForExtension`, plus `displayGroups`, the same
  groups in the order the app lists them for a reader, Documentation first, which a view
  that lists groups uses; compare a rollup’s `registry` identity before combining it
  with labels or colors from here;
- `icons` and `icons.withClass`;
- `filterControls` for the host’s accessible filter chips and menus, and for any
  exclusive choice among labelled values;
- `shortcuts.attach(element, spec)`; see [Keyboard Shortcuts](#keyboard-shortcuts);
- `menus.dismissible(menu)`, how every menu closes; see [Menus](#menus);
- `chart(container, type, data, options)`, `ensureAsset(name)`, `ensureModule(name)`,
  `moduleUrl(name)`, and `ensureKindAssets(kind)`, below;
- `whenIdle(callback, {timeout})`, which runs `callback` when the page is free, no later
  than `timeout` milliseconds, and returns a canceller
  ([Idle Work](project/architecture/arch-browser-shell.md#idle-work));
- `sourceKind()` for the served source (`filesystem` or `git_revision`).
- `capabilities()` for the trust profile the page was served under,
  `{activeContent, mutations}`; a pinned revision’s page is always inert, and an inert
  page’s policy blocks frames and `<embed>` (`untrusted_shell_csp` in
  `capabilities.py`);
- `host.supports(action)` and `host.actions()` for what the page’s host does beyond a
  browser, by action name, from the `window.metabrowserHost` the host defines.
  A browser defines none.
  The macOS app defines `open-file`: it opens an `<a data-metabrowser-open-file>` link’s
  file in the app the system assigns to its type (`builtin_plugins/pdf/index.js` draws
  one). Ask about an action, never about which host the page is in.
  The view compositor installs `capabilities()` and `host`, so a view reads them from
  its render on, not at load.

A view that draws tabs of its own uses the host’s `.tab-btn` in a `.tab-bar`, with
`<a class="tab-btn" href>` for a tab that is an address, and positions but does not
restyle them ([The Tab Bar](design-system.md#the-tab-bar)). A control that shows or
hides content carries the host’s `disclosure-toggle` class so clicking it never selects
text; a native `summary` needs nothing
([Disclosure Toggles Never Select Text](design-system.md#disclosure-toggles-never-select-text)).

A menu a view draws on the host’s `.menu` surface heads each group of its rows with the
host’s pattern: a `.menu-group` with `role="group"` and `aria-labelledby` naming its
`.group-heading`, which draws its own divider and starts on the menu’s row inset.
A menu whose rows are all one group is named from that heading instead, through the
menu’s own `aria-labelledby`. `filterControls.bind` fits a dropdown to its rows and the
window when its trigger opens it and when the window resizes; a view that renders one
open another way calls `filterControls.fitOpenMenus(root)` after rendering.
See [Groups in a Menu](design-system.md#groups-in-a-menu) and
[Menu Height](design-system.md#menu-height).

`filterControls.bind` also moves focus with a dropdown.
Every way its trigger opens the menu (a click, Enter, Space, `↓`, or `↑`) focuses the
checked row, or else the first.
Escape, a second click on the trigger, or a choice that closes the menu gives focus back
to the trigger. An Escape that a surface above has already handled, as Quick Search and
Help do, leaves the menu open.
A bound dropdown closes as every menu does ([Menus](#menus)): a press elsewhere in the
bound container closes it too, once the control it landed on has acted.
A view that opens a menu from its own state focuses it with
`filterControls.focusMenu(root, key)`. A view that rebuilds the markup it bound calls
`filterControls.keepFocus(root)` before the rebuild and the function it returns after,
so focus goes back to the control that had it, or to the trigger of a menu the rebuild
closed. `filterControls.activateMenuRow(row)` chooses a row as a click on it does.
A row’s `key` option, and the menu’s `anyKey`, name the letter that chooses that row
while the menu is open and has focus, as a `data-menu-key` attribute on the row.
Only the shell reads that attribute, and only in the Files filter bar, so in a plugin’s
menu the letter does nothing yet.
See [Keys in a Menu](design-system.md#keys-in-a-menu).

A view whose toolbar stands in the navigation’s toolbar slot, as the Pulls tab’s does,
gives its row of controls the host’s `nav-toolbar-row` class, which wraps the row
between its controls when the pane is too narrow for one line and spaces its lines by
the toolbar’s tokens; a control that ends the row takes the line’s end with
`margin-inline-start: auto`. Bound there, `filterControls.bind` keeps each joined group
fitted to its line: one the line cannot hold takes the cluster layout until it can, and
`filterControls.fitJoinedGroups(root)` fits them at once.
See [Navigation Toolbars Wrap](design-system.md#navigation-toolbars-wrap).

A view that shows a message about the content, such as a description or a comment, plain
or as Markdown, puts the host’s `chrome-prose` class on the element that holds the text,
never on its page, and sets no face of its own: chrome prose is sans under either
reading font, and a document shown beside it keeps the reader’s reading font.
A view whose container carries `md-body` gets the reading font on its Markdown’s
headings, paragraphs, lists, and quotes only, so anything else it draws, such as a
toolbar or an empty state, keeps the chrome face without a face of its own
([Serif Is for Documents](design-system.md#serif-is-for-documents)).

`ensureAsset(name)` loads a vendored library the shell does not put on every page, and
resolves once its globals are present.
Await it before touching the library: a loaded bundle resolves immediately, simultaneous
callers share one load, and it rejects for an unknown name or a failed script, so a view
can say so.
The bundles are named in `on_demand_script_bundles` in `server.py`; `"chart"`
is Chart.js with its annotation plugin and date adapter.
`ensureModule(name)` is its counterpart for a bundle that is one ES module, declared
there as `{"module": url}`, such as `"mermaid"`: it imports the module once and resolves
to its namespace, so read the library from what it returns rather than from a global.
Simultaneous callers share one import, a failed import rejects and the next call imports
again, and a name that is not a module bundle, a script bundle’s among them, rejects.
`moduleUrl(name)` is the same bundle’s absolute URL, or `null` for a name that is not a
module bundle: what a frame of the plugin’s own imports to run the module in that
frame’s realm, where the namespace `ensureModule` returns cannot reach.
[Asset Loading Tiers](project/architecture/arch-browser-shell.md#asset-loading-tiers)
says which tier an asset belongs in.

`ensureKindAssets(kind)` loads the plugins that declare a view for a kind.
Await it before embedding one kind’s renderer inside another plugin, then read the
renderer from the SDK. It rejects only when the SDK’s own view helpers or template
library could not be fetched, before any plugin code ran, and a retry tries again; a
plugin whose own assets fail is logged and skipped.

Use `renderSourceView` when several kinds need the same raw-source presentation, rather
than depending on another kind’s plugin.
The shell runs `<code>` syntax enhancement after default and lazy-mounted renderers
settle, and again when the prefetched grammars arrive.
A custom Source renderer preserves exact text, uses `langForPath`, and adds
`no-highlight` only to apply a host-provided degradation decision.
Plugins do not read `METABROWSER_SETTINGS` or call the Highlight.js global directly.

`chart(container, type, data, options)` throws unless
`await metabrowser.ensureAsset("chart")` ran first.
Chart color fields may use design-token references such as `var(--chart-series-info)`,
which the SDK resolves for the current palette and updates when the theme changes.
Call the returned instance’s `destroy()` from `dispose` to release Chart.js and the
theme subscription.

Build DOM elements and attach listeners rather than writing inline handler strings, and
keep cleanup handles in the renderer closure.
Place `fileTypeIcon()` output in the shared `.file-identity-icon` box, marked
decorative; it is trusted host chrome, so never pass user-provided markup through it.

### Data and Navigation

- `fetchPluginData(plugin, route, params, options?)` calls a declared data hook with
  `GET`; pass `{ signal }` so a disposed view aborts its request.
  A parameter whose value is an array is repeated, one value each, as the table rows
  route takes `cols`; a `null` or `undefined` value is left out.
  A non-ok response rejects with an `Error` carrying `status` and the parsed `payload`.
  Call a `POST` hook with `fetch`.
- `fetchJsonl(path, options)` requests a normalized JSONL envelope.
- `fetchCompleteText(ctx, options)` retrieves a bounded complete source after an initial
  text envelope reports truncation, and `fetchText(target, options)` does the same for a
  navigation target, forwarding an optional abort signal.
- `fetchKpressRender(ctx, view, options)` requests a KPress-rendered view, and
  `loadKpressAssets()` loads the KPress browser assets once.
- `loadChangedFilesTree()` loads the shell’s tree of a change set’s files once, on
  demand: folders built from paths with their line counts rolled up, the visible rows,
  which folders are open, a change set’s header text, and `displayPath`. A diff’s Diff
  summary and the Pulls tab’s changed files both draw with it;
  `static/changed-files-tree.js` documents each function.
- `renderTextTruncationWarning(data)` preserves visible truncation warnings.
- `eventReports`, once `await mb.ensureAsset("event-reports")` has loaded it, tells the
  event log what the page waits for
  ([What the Page Reports](realtime-debugging.md#what-the-page-reports)).
  `eventReports.wait(name, { startedAt, detail, onLate })` names a wait that reports
  nothing unless it has run `eventReports.lateMs` while the page was shown; then it is
  reported, `onLate(ms)` lets the view say so, and the handle’s `end(outcome)` reports
  how it ended. Pass the `performance.now()` at which the wait began as `startedAt`,
  since the bundle may arrive later, and end every wait from `dispose`, as
  `never_completed` when the reader leaves first.
  `eventReports.showDetails(panel, query, { signal })` paints into *panel* what the
  event log holds for `{ client, since, until }`: `client` is `eventReports.page` for
  this page’s own records, and a failure’s window can be `eventReports.failureWindowS`
  seconds before it ended, the window the failure’s recent count covers.
- `navigation.href(target)` returns the canonical `/view/` URL for a
  `{ path, query?, fragment? }` target, whose path is served-root-relative with `/`
  separators and no leading slash; the empty path selects the served root.
- `navigation.open(target, options?)` performs normal user navigation and returns a
  promise. `{ viewId }` prefers a view the destination declares, falling back to its
  default, without changing the URL. When the destination is the file already shown, it
  selects that view of it, as its tab does, which is how a view takes a person to
  another view of the same file.
  `{ replace: true }` replaces the current history entry instead of pushing one, for a
  step Back should not stop at, such as the text typed into a search field.
- `navigation.current()` returns the current target, or `null` on the landing URL.
- `fileCatalog.snapshot()` returns an immutable view of the files the shell knows, as
  canonical logical-file paths ordered by UTF-16 code units, with no global path-length
  ceiling. `complete` means the walk finished under its file cap, so the catalog lists
  every file; `truncated` means it stopped at the cap, so a missing path is not proof of
  absence; while both are false the walk is running.
  A plugin waiting for a final catalog stops on either flag, as the Markdown built-in
  reports unresolved links as `catalog-truncated`, and keeps its subscription, since a
  restart with a higher cap can still complete a walk.
- `fileCatalog.subscribe(listener)` invalidates inventory-derived plugin results and
  returns an unsubscribe function for the view’s disposer.
- `repository` is `null` or the served tree’s frozen, public-safe GitHub identity: host,
  owner, repository, exact revision, current branch, and served subdirectory, never a
  local path.

Use `navigation.href()` for real anchor `href` values so status previews, copy-link,
modifier clicks, new tabs, and reloads keep native behavior, and call
`navigation.open()` only for an unmodified in-app activation:

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
  `/api/rollup`; `depth: 0`, `top: 0`, and `ext_rank: "dual"` give a tally-only
  count-and-byte summary.
  `depth: "max"` and `top: "max"` ask for the deepest and widest tree the route serves
  (`ROLLUP_MAX_DEPTH` and `ROLLUP_MAX_TOP` in `src/metabrowser/settings.py`), which the
  route resolves and its node budget bounds, as the Treemap does.
  `filename_top` and `remaining_top` default to, and cannot exceed,
  `ROLLUP_FILE_TYPE_FILENAME_LIMIT` and `ROLLUP_FILE_TYPE_REMAINING_LIMIT` in
  `src/metabrowser/settings.py`. None of `nodes`, `ignored`, and `encoding` is sent
  unless named; the route clamps `nodes` as it does `depth` and `top`, and answers 400
  for an unknown `ignored` or `encoding`:
  - `nodes` is the node budget, a positive integer or `"max"`: `ROLLUP_DEFAULT_NODES`
    unless named, and at most `ROLLUP_MAX_NODES`. The route expands the heaviest folders
    first, and each may spend a share of the budget left in proportion to the files and
    folders beneath it (`_emit_limit` in `src/metabrowser/inventory_rollup.py`), so a
    budget that covers the tree emits all of it.
    A folder the budget did not reach has `children: null`; one whose children ran past
    `top` or its share keeps those it emitted and a `rest` bucket for the others.

  - `ignored: "exclude"` leaves gitignored entries out of `children` and `rest`, and
    they spend none of the budget; a folder that is ignored is not a child at all.
    Everything else is as with `"include"`, the default: every total, tally, breakdown,
    and `dominant_ext` still counts the ignored files.

  - `encoding: "compact"` keeps only folders in an expanded folder’s `children` and
    writes its files as `files` entries, `[name, size, mtime, ext, gitignored]`, with
    `mtime` null where it is omitted and `gitignored` 0 or 1; the envelope says
    `"encoding": "compact"`. A folder with `children: null` has no `files`. A file’s
    path is `dir.path ? dir.path + "/" + name : name`. A pinned Git revision’s paths are
    not, so a pin answers the default encoding, with no `encoding` key: read the key,
    not the request. The SDK returns the body as served, and the folder plugin decodes
    it. `cli-api-rollup-dense.tryscript.md` pins each of these on a real folder:

    ```json
    {
      "path": "src",
      "encoding": "compact",
      "node": {
        "name": "src", "path": "src", "type": "dir", "total_files": 10,
        "children": [
          {"name": "lib", "path": "src/lib", "type": "dir", "children": null}
        ],
        "files": [
          ["main.py", 200, 1700000000.0, ".py", 0],
          ["run.log", 60, 1700000000.0, ".log", 1]
        ]
      }
    }
    ```
- `watchRollup(path, options, onUpdate)` fetches and then refreshes after relevant
  inventory changes. Supply `active` to gate hidden views and `onError` for a local
  failure state; always call the handle’s `dispose()`, and call `refresh()` when
  `stale()` is true after activation.
- `directoryTotals.get(path)` and `directoryTotals.subscribe(path, listener)` read the
  shell’s live directory totals without a request.
- `onInventoryChange(listener)` passes each observed change’s inventory paths, every
  changed entry with each ancestor whose totals it moved down to the depth the shell
  watches, and returns an unsubscribe function.
  It passes `null` when anything may have changed: the stream reconnected or
  resynchronized, or the first crawl finished.
  A host with no inventory stream never calls it.
- `watchFile(path, {generation, onChange, onState})` watches one file through the page’s
  event stream, whether or not the inventory reports it (an ignored file, a deep one, a
  database whose owner writes through its log), and returns a disposer.
  Pass the `generation` your read answered, such as a table page’s, so a change before
  the watch is registered still reaches you; `onChange({path, generation})` is called
  once for each change the server polls, with `generation` null when the file is gone.
  `onState(state, reason)` says whether the watch is `waiting` for a connection, `live`,
  or `refused`, as past the per-page bound `FILE_WATCH_MAX_PATHS`
  (`src/metabrowser/file_watches.py`). A page with no stream, such as a pinned
  revision’s, never calls either.
  Call the disposer when the view goes; the shell registers every watch again on each
  new connection
  ([File Watches](project/architecture/arch-live-delivery.md#file-watches)).
- Each `ext_tallies` row is
  `[extension, all_files, all_bytes, unignored_files, unignored_bytes]`. The empty
  extension is the aggregate **Other** tail; `(none)` is the extensionless category.
- `file_type_breakdown` is the File Rollup Format result: registry identity, exact `all`
  and `unignored` populations, ordered group and family rows, canonical-extension
  children, and bounded No extension and `remaining_types` children with exact
  remainders, shown as **Other types**.

### Keyboard Shortcuts

`shortcuts.attach(element, spec)` gives one of a view’s controls a letter key or, with
`numbered: true`, a positional number.
The key does what the control does, Help lists it, and while the reader holds Shift a
keycap badge sits on the control.
Which kind of key a control should have, and which letter, follows
[Keyboard Shortcuts](design-system.md#keyboard-shortcuts) in the design system: a letter
for a known meaning, a number for a situational link or action, and no key for an
ancillary one such as copying.
Feature-detect it with `mb.shortcuts?.attach`:

```javascript
const handle = mb.shortcuts?.attach(toggle, {
  id: "example.layout", // dotted; one id is one command, however many controls carry it
  key: "l", // one ASCII letter, in either case
  group: "controls", // "controls" or "view-tabs", the Help group it is listed in
  order: 10,
  copy: { action: "Toggle layout", description: "Switch the layout.", hint: "Layout" },
  activate: () => toggleLayout(view), // the control's own path, never a synthesized click
  signal, // optional AbortSignal; aborting it detaches
});
handle?.retarget(nextToggle); // the control was rebuilt as another element
handle?.detach(); // idempotent; call it from dispose()

const refresh = mb.shortcuts?.attach(refreshButton, {
  id: "example.refresh",
  numbered: true, // its number is its place among the screen's numbered controls
  activate: () => refreshView(view),
  signal,
});
```

A numbered control’s number is its place, in document order, among the live numbered
controls on the screen, the shell’s and every plugin’s, from `1` to `9`; it is read when
a digit is pressed or the reveal shows, so it changes as controls come and go, and a
tenth control has none.
Help lists the numbers once, as one row.
A numbered spec takes only `id`, `numbered`, `activate`, and `signal`.

- A view may attach at any time, even before the shell’s keyboard support has loaded:
  the key takes effect once it has, and survives the shell rebuilding it.
- The key is live only while its element is connected, visible, enabled, and outside an
  `inert` subtree, so a staged view’s keys wait for it to be shown.
  Removing the element does not end the attachment; when a rebuild replaces it, call
  `retarget()` with the new one.
- Shift does not change the key, Ctrl, Alt, and Meta are never part of it, and it does
  not fire in a text field or on key repeat.
  Every shell key outranks it, and Help and Quick Search silence it while open.
- Malformed input throws an error whose message starts with `shortcuts.attach:`, such as
  an element that is not an `HTMLElement`, a key that is not one letter, an unknown
  group, a missing `activate`, a letter option beside `numbered: true`, or an id
  attached already with other settings.
  An attachment made before the keyboard support loads is checked then, and a malformed
  one is logged with `console.error` instead.
- A letter in `RESERVED_SHELL_KEYS` in `src/metabrowser/keymap.py` is refused with one
  console warning and no error, so a view keeps working if the shell reserves another
  letter later. Digits are reserved for `numbered: true`.
- When two shown controls hold one letter, a shell key beats a plugin key, and between
  plugins the earlier attachment wins and the console warns once for the loser.
  Two mounts of one id are one command, and the first shown in document order runs.
- Detach every attachment from `dispose()`, or pass the view’s `AbortSignal`. The shell
  also releases the keys inside a view container it disposes, but a view a host mounts
  by calling its renderer directly, as three hosts mount the diff view, has only its own
  `dispose()`.

### Menus

Every menu closes alike, as
[Every Menu Closes Alike](design-system.md#every-menu-closes-alike) says: a press or a
tap outside it and its trigger, focus arriving outside them, the window losing focus (to
a preview’s frame or another application), and Escape close it, and opening one menu
closes any other. The press that closes a menu still acts on what it lands on.
A dropdown that `filterControls.bind` draws closes so already.
`bind` answers for every dropdown inside the element it is given, so bind each control’s
own element, never a region that holds another bound control: the outer binding would
take that control’s open dropdown for its own and close it.
A view that draws a menu of its own gives it that closing with `menus.dismissible`, and
feature-detects it with `mb.menus?.dismissible`:

```javascript
const closing = mb.menus?.dismissible({
  name: "example-menu", // the surface's own class beside `menu`
  trigger: button, // or a function that finds it after a rebuild
  inside: (node) => panel.contains(node), // the panel, and anything it places elsewhere
  isOpen: () => !panel.hidden,
  close: (how) => setOpen(false), // "outside", "away", "escape", or "other"
});
button.addEventListener("click", () => {
  setOpen(panel.hidden); // the trigger's own click toggles, so a second press closes
  if (!panel.hidden) closing?.opened();
  else closing?.closed();
});
closing?.dispose(); // from dispose(), when the menu goes for good
```

- Call `opened()` from every path that opens the menu, a key as well as a click, and
  `closed()` when the view’s own code closes it.
  `opened()` closes any other open menu, whichever handle holds it, so one menu has one
  handle. The listeners are held only while a menu is open.
- `opened()` moves focus to the trigger when focus is outside the menu and its trigger,
  as a press in Safari leaves it; a view that puts focus into the menu does so after the
  call.
- `close(how)` closes the menu as the view’s own code does.
  For `"escape"` the helper then gives focus back to the trigger, unless `close` already
  moved it there; for the other reasons focus stays where the press or the key put it.
- Escape closes the menu opened last, and is prevented when it does.
  An Escape a surface above the menu already prevented, or one held with Alt, Ctrl, or
  Meta, leaves it open.
  The view keeps its own keys inside the menu: its arrows, letters, and Tab.
- The helper arrives with the shell’s tools, after the first tree.
  A menu opened sooner asks for them and closes alike once they land.
- The trigger is part of the menu, so its own click decides what a press on it does;
  `inside` names the rest.
  A press anywhere else closes it, but a drag that starts inside the menu, as in
  selecting a field’s text, does not, wherever it lets go.
- Focus that a press inside the menu moves does not close it, until that press is over:
  at its click, the next press, or a key, and, for a press that brings no click, a task
  after a mouse’s or a pen’s button comes up, or at once on `pointercancel` or
  `contextmenu`. A touch that brings none of those ends at the next press or key.

### Folder Overview Contributions

The built-in folder plugin publishes `mb.folderOverview` before installed plugins load.
Use it when a capability summarizes a folder inside **Overview**; a primary working mode
remains a normal `registerView("folder", ...)` tab.

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
`placement` is `summary`, `content`, or `supplemental`; placement order and then the
panel ID determine layout.
`presentation` is `surface` for a flat host-rendered panel body or `document` when the
renderer owns its document surface.
The Overview composer supplies the section heading and text alignment for both, so a
mount does not repeat the heading or add a disclosure.
Set `required: true` only when returning null is a contract error.
A resolver returns `{key, data}` or null; a matching key keeps a mounted panel and calls
its optional `update(ctx, data)`. Resolvers and mounts receive abort signals, a failure
stays local to its panel, and every disposer must be idempotent.
`listPanels()` returns the frozen descriptor list.

`mb.folderContext.subscribe(path, onUpdate)` gives the folder envelope, which the shell
seeds and multiplexes so subscribers start no parallel `/api/file` refreshes;
unsubscribe on disposal.
`mb.viewState.isActive(container)` and `subscribeActive(container, listener)` let a lazy
view defer hidden work, and a composite renderer calls
`mb.setViewPrintState(container, state)` when its printability changes.

The Markdown plugin’s
`mountRendered(container, ctx, {signal, pagePath, printIndicator})`, from
`await mb.plugins.load("markdown")` with `requires = ["markdown"]`, mounts a Markdown
document panel with the ordinary KPress presentation, its table of contents included.
`pagePath` names the page that shows the document as its own when that is not the
document’s path, as a folder’s Overview shows its README: the document’s fragment links
and table-of-contents entries are then places on that page.
`printIndicator: true` puts a print button in the corner of the document’s card, for a
view whose print is the document itself; it is off unless the host asks
([Print](design-system.md#print)). Its handle aborts its request and disposes its table
of contents, print button, enhanced-link listeners, pending fragment work, and nested
Obsidian transclusions.
Transclusions share depth, document, source-byte, cycle, abort, and disposal limits
across the mounted document, and each embed’s time limit starts when that embed begins
loading. Do not copy Markdown DOM or table-of-contents behavior into a contribution.

Its `drawDiagrams(root, {inert, isolated})` draws the Mermaid diagrams of a KPress
render your plugin placed under `root`, as the Markdown view draws its own: an inert
render’s `<pre lang="mermaid">` blocks become images, and only `inert: false`, for a
render the reader trusts, puts the SVG in the page.
It returns null, and loads nothing, when `root` holds no diagram; otherwise its
`dispose()` stops drawing and leaves the figures as drawn, so call it when you replace
`root`. Mermaid lays an image out in a document before it becomes one, and there a
diagram’s own CSS can load an image, so a plain image is laid out in the page and
bounded only by the page’s policy.
For untrusted text on a page that may have none, such as a folder’s page served trusted,
pass `isolated: true`, as a pull request’s page does: the images are laid out in a frame
whose own policy loads nothing (`builtin_plugins/markdown/diagram-frame.js`;
[Inert Markdown](project/architecture/arch-server-and-content.md#inert-markdown)).

### The SDK Version

The SDK is versioned with the release, and the version is enforced.
`PLUGIN_SDK_VERSION` in `plugin_loader/manifest.py` is the contract this host provides.
A manifest whose resolved `sdk_version` differs, including one that omits the field, is
refused when it loads, with a message naming the required version, and `metab --doctor`
reports the same problem first.
There is no negotiation and no shim for an older surface: update the plugin against the
release it targets and set `sdk_version` to match.
A break is recorded in `CHANGELOG.md`, and until its release in
[`changelog.d/`](../changelog.d/README.md);
[Compatibility and Legacy Code](development.md#compatibility-and-legacy-code) explains
the policy.

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

Ensure the wheel includes the manifest, JavaScript, CSS, and any extra assets, and test
the built wheel in an isolated environment, since an editable checkout can conceal
missing package data.

### Python Registration Module

A built-in or installed entry-point plugin that registers Python-side extensions, such
as a JSONL adapter, names the module that does it in its manifest:

```toml
[plugin]
name = "example-plugin"
register = "example_plugin.adapters"
```

Discovery imports that module once, when it finds the plugin, so the module’s top-level
calls (`register_log_adapter` and the like) run before the server mounts anything.
A module that fails to import is a plugin load error, reported as the others are: the
plugin is skipped and `metab --doctor` exits nonzero.
An operator-directory plugin is JavaScript-only, so its `register` is ignored with a
warning, and `metab --doctor` reports it.
The module should import from `metabrowser.plugin_api` and do nothing but register.

### Plugin-Owned JSONL Adapters

Plugins that recognize an additional JSONL event format can register a detector and
parser factory when their `register` module loads
([Python Registration Module](#python-registration-module)). The built-in `agents`
plugin registers its Claude Code, Codex, Pi, and Gemini adapters the same way, so
`registered_log_adapters()` lists every name in detection order:

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

The detector receives parsed objects from the beginning of the stream; keep it fast,
deterministic, and free of filesystem or network work.
A format whose stream opens with plain text can also pass `line_detector`, which
receives each opening line that is not a JSON object.
Detection asks each line’s detectors in registration order, the built-in `agents`
plugin’s first, so a detector should recognize only its own format.
A detector failure is logged and skipped, so one adapter cannot break detection for
every JSONL file. Registering the same callables again is idempotent; claiming a name
already registered, the built-in plugin’s or another plugin’s, raises an error.
Adapters register when plugins are discovered, which the server does at startup, so a
script that calls `detect_adapter` without starting the server sees only the adapters it
registered itself. A log that no registered adapter recognizes gets the `unknown`
adapter, whose parser turns each JSON object into an event of its `type`. The factory
returns a fresh parser for each file or live stream.
A `[[kind]]` rule with `match = { ext = ".jsonl", adapter = "example" }` then claims the
files the detector recognizes.

### Python Sidekick API

Import server-integrated helpers from `metabrowser`, not private package modules.
`metabrowser.plugin_api.__all__` lists them, and `metabrowser.__all__` adds `CLIError`,
which a CLI integration can catch to keep a command’s message and exit code, and
`__version__`.

- **Content:** `resolve_content`, `resolve_content_container`, `stat_content`, and
  `read_content_window`, returning `ContentRef`, `ContentStat`, and `ContentWindow`, are
  the source-agnostic reader under [Reading Content](#reading-content).
  Every read takes an explicit byte maximum.
  They raise `ContentReadError`, with `ContentUnavailableError` for content that
  resolved and then could not be read.
- **Filesystem:** `resolve_path(value)` resolves a served-root-relative identity and
  rejects traversal; the empty string is the served root.
  `resolve_directory(value)` also requires a directory, `served_root()` returns the
  root, and `relativize_path(value)` turns a native path under it back into an identity.
  These and `open_content` are filesystem-only: on a subject with no filesystem root
  they raise `UnsupportedSourceCapabilityError`, and `source_capabilities()` and
  `require_source_capability()` report what the subject can do.
- **Compressed artifacts:** `ArtifactPath` reads supported single-file compression
  transparently, within decompression limits, and raises `ArtifactCompressionError`,
  `ArtifactDecompressionLimitError`, or `ArtifactDecompressionTimeoutError` to separate
  malformed data from size and time limits.
- **JSONL:** `LogEvent`, `LogParser`, `detect_adapter(lines)`, `create_parser(adapter)`,
  `register_log_adapter`, and `registered_log_adapters()` are the adapter contract
  above. Use `create_parser` to instantiate a registered adapter for each stream.
  Built-in `agents` imports these from `metabrowser.plugin_api`, and
  `tests/test_agents_import_boundary.py` holds it to that.
  `jsonl_parse_max_bytes()` is the parser’s decompressed input limit, so a hook reads at
  most that many bytes of a log.
  `extract_agent_charts_cached(path)` reuses the agent-log chart projection, returning
  `None` for an absent file and raising `JsonlParseLimitError` past the parser’s input
  limit. `extract_agent_charts_bytes(data)` projects bytes already read, and
  `lookup_agent_charts` and `remember_agent_charts` memoize a projection by a content
  reference’s identity and fingerprint.
- **Cache:** `plugin_cache_directory(name)` creates or verifies the plugin’s owner-only
  directory under the application cache root and returns it.
  It is a cache: a user may delete it at any time, so key what it holds by what it was
  computed from. It raises `PluginCacheUnavailableError` when no private cache root can
  be made.
- **Lifecycle:** `register_root_callback(callback)` invalidates plugin caches when the
  served root changes.
- **Table sources:** `TableSource`, `TableHandle`, and the types, errors, cell and token
  helpers, and bounds a source implements, under [Table Sources](#table-sources).
  The table routes’ own wiring stays in `metabrowser.table_source`. Do not cache the
  resolved root, or import underscored helpers from `metabrowser.paths_safe`.

The sidekick surface is provisional during the 0.x series, and release notes identify
its changes. Plugin-loader and manifest types are available from their defining modules
but are not part of this contract.

## Testing Checklist

Before publishing a plugin:

1. Run `metab --doctor` in a clean environment.
2. Confirm every manifest view has a matching `registerView` call.
3. Exercise default and lazy-mounted tabs, including any post-mount syntax enhancement.
4. Verify `dispose` stops listeners, streams, timers, and chart instances.
5. Verify every `shortcuts.attach()` attachment detaches in `dispose`, and that using
   the view prints no `shortcuts.attach:` warning or error in the browser console.
6. Test path validation and malformed data-hook inputs.
7. Build the wheel and confirm all static assets are present.
8. Browse data with the plugin absent to verify core fallbacks remain usable.

See [end-to-end testing](e2e-testing.md) for the repository’s browser-side contract
tests.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
