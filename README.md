# MetaBrowser

MetaBrowser is a local web UI for exploring files, live logs, JSONL streams, Markdown,
structured data, images, and binary metadata.
Point it at a directory or file and it opens a browser with a live file tree and
extensible preview tabs.

MetaBrowser is an MIT-licensed Python package for Python 3.12 and newer.
Markdown is rendered by the exact `kpress==0.2.2` dependency.

## Quick Start

MetaBrowser uses [uv](https://docs.astral.sh/uv/). Run the latest published release
without installing a global tool:

```shell
uvx metabrowser ./path/to/artifacts
```

For a reproducible run, pin the release:

```shell
uvx metabrowser@0.1.0 ./path/to/artifacts
```

To make MetaBrowser available everywhere as `metab`:

```shell
uv tool install metabrowser==0.1.0
metab ./path/to/artifacts
```

`metab` is the standard installed command.
The `metabrowser` compatibility command matches the package name, which is why the short
`uvx metabrowser ...` form works.

The CLI documents every command and option:

```shell
metab --help
metab serve --help
metab plugins --help
```

See [installation](docs/installation.md) for uv setup and upgrade instructions.

To run an unreleased source checkout, install its exact locks and invoke the local
environment without resolving them again:

```shell
make install
uv --config-file uv.toml run --frozen metab ./path/to/artifacts
```

## What MetaBrowser Opens

Built-in plugins provide views for:

- Markdown rendered by KPress, alongside the source
- JSON, YAML, and other structured documents
- coding-agent JSONL logs and generic JSONL streams
- text, source code, images, and binary-file metadata
- generic chart summaries for supported agent logs

Gzip and zlib variants of supported artifacts open transparently with bounded
decompression. Format-specific binary stores belong in separately installed plugins,
keeping native readers out of the core package.

Large trees are indexed in the background.
The first preview does not wait for a full recursive crawl, and filesystem events update
the tree and recent-file views while the server runs.

## Common Commands

The short form starts the local server, opens the browser, and serves the selected root:

```shell
# Browse a directory or open one file directly.
metab ./path/to/artifacts
metab ./path/to/artifacts/logs/session.jsonl

# Select a file relative to the served root.
metab ./path/to/artifacts --path logs/session.jsonl

# Start without opening a browser window.
metab serve ./path/to/artifacts --no-open

# Browse a directory on a remote host through an SSH tunnel.
metab remote example-host --path /srv/artifacts

# Print a machine-readable inventory without starting the web UI.
metab walk ./path/to/artifacts --format json
```

The server binds to `127.0.0.1:8411` by default and walks a bounded port range if that
port is occupied. Review the security implications before changing `--host` to expose a
served root beyond localhost.

## Plugins

MetaBrowser is designed to be extended.
A plugin can add:

- file-kind matching rules
- browser preview tabs implemented in JavaScript
- optional Python data hooks for installed plugin packages
- JSONL event adapters for additional log formats

Inspect the complete registry and validate every discovered plugin from the CLI:

```shell
metab plugins list
metab plugins list --json
metab plugins show markdown
metab plugins doctor
```

MetaBrowser loads plugins only from trusted sources:

1. built-ins shipped in the MetaBrowser wheel
2. installed Python packages registered in the `metabrowser.plugins` entry-point group
3. directories explicitly named with `--plugins-dir` or `METABROWSER_PLUGINS_DIRS`

An installed Python plugin must be present in the same uv tool or uvx environment as
MetaBrowser. Operator-directory plugins are useful for local JavaScript-only extensions.

For example, load an operator-reviewed plugin directory with:

```shell
metab serve ./path/to/artifacts --plugins-dir ./trusted-plugins
```

The served data tree is never an implicit plugin source.
See the [plugin authoring guide](docs/plugins.md) for the manifest schema, browser SDK,
packaging, lifecycle rules, and security boundary.

## Use With Coding Agents

MetaBrowser includes a portable [Agent Skill](skills/metabrowser/SKILL.md).
Install it for supported coding agents with:

```shell
npx skills add jlevy/metabrowser --skill metabrowser
```

The skill requires no persistent MetaBrowser installation.
It calls the pinned `uvx metabrowser@0.1.0 ...` runner and uses `--help` on the CLI and
its subcommands as the source of truth.
A globally installed `metab` remains available as the faster local command.

## Develop

The repository uses uv, Ruff, BasedPyright, pytest, Biome, TypeScript check-JS, and
Flowmark:

```shell
make install
make format
make verify
```

`make verify` checks formatting, lint, types, tests, locked dependency audits, source
and wheel builds, artifact inspection, and isolated installed-wheel smoke tests.
See [development](docs/development.md) and [architecture](docs/architecture.md).

## Documentation

- [Installation](docs/installation.md)
- [Plugin authoring](docs/plugins.md)
- [Architecture](docs/architecture.md)
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
