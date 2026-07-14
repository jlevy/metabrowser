# MetaBrowser

MetaBrowser is a local web UI for exploring files, live logs, JSONL streams, Markdown,
structured data, images, and LMDB databases.
It combines a responsive file tree with extensible preview tabs, live filesystem
updates, and trusted plugins.

Markdown rendering is provided by the exact `kpress==0.1.0` dependency.
MetaBrowser ships as an MIT-licensed Python package for Python 3.12 and newer.

## Install

Run the published CLI without a persistent installation:

```shell
uvx --from metabrowser==0.1.0 metabrowser ./path/to/artifacts
```

Or install the command with uv:

```shell
uv tool install metabrowser==0.1.0
metabrowser ./path/to/artifacts
```

See [installation](docs/installation.md) for uv setup.

## Use

The short form starts a local server, opens the browser, and serves the selected root:

```shell
metabrowser ./path/to/artifacts
```

Useful forms include:

```shell
# Open one file within the served root.
metabrowser ./path/to/artifacts --path logs/session.jsonl

# Start without opening a browser window.
metabrowser serve ./path/to/artifacts --no-open

# Inspect files on a remote host through an SSH tunnel.
metabrowser remote example-host --path /srv/artifacts

# Inspect and validate the plugin registry.
metabrowser plugins list
metabrowser plugins doctor

# Print a machine-readable inventory without starting the web UI.
metabrowser walk ./path/to/artifacts --format json
```

The server binds to `127.0.0.1:8411` by default.
If that port is occupied, MetaBrowser walks a bounded range to find the next available
port. Use `--host` and `--port` to override the defaults; review the security
implications before exposing a served root beyond localhost.
Remote mode also waits for the tunneled HTTP endpoint to become ready before opening the
local browser.

## Built-In Views

MetaBrowser includes trusted plugins for:

- Markdown rendered by KPress, with a source view;
- JSON, YAML, and other structured documents;
- coding-agent JSONL logs and generic JSONL streams;
- text, source code, images, and binary-file metadata;
- LMDB database inspection;
- generic chart summaries for supported agent logs.

Large trees are indexed in the background.
The initial file preview does not wait for a full recursive crawl, and filesystem events
update visible rows and recent-file views while the server is running.

## Plugins

A plugin combines a declarative `manifest.toml` with browser-side renderers in
`index.js`. Installed Python distributions may also provide server-side data hooks.
MetaBrowser loads plugins only from trusted sources:

1. built-ins shipped in the wheel;
2. the `metabrowser.plugins` Python entry-point group;
3. directories explicitly named with `--plugins-dir` or `METABROWSER_PLUGINS_DIRS`.

The served data tree is never an implicit plugin source.
See the [plugin authoring guide](docs/plugins.md) for the manifest schema, JavaScript
SDK, entry-point registration, lifecycle rules, and security model.

## Develop

The repository uses uv, Ruff, BasedPyright, pytest, Biome, TypeScript check-JS, and
Flowmark:

```shell
make install
make format
make verify
```

`make verify` runs check-only formatting and lint gates, the complete test suite,
locked-graph vulnerability audits, wheel and source builds, artifact inspection, and an
isolated wheel-import smoke test.
See [development](docs/development.md) and [architecture](docs/architecture.md).

## Documentation

- [Architecture](docs/architecture.md)
- [Plugin authoring](docs/plugins.md)
- [Design system](docs/design-system.md)
- [End-to-end testing](docs/e2e-testing.md)
- [Real-time debugging](docs/realtime-debugging.md)
- [Development](docs/development.md)
- [Publishing](docs/publishing.md)
- [Security policy](SECURITY.md)

## License

MetaBrowser is available under the [MIT License](LICENSE).

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
