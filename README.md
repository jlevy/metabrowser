# Metabrowser

Metabrowser is an extensible, plugin-based local file browser.
Use it where you might use an IDE or OS file manager, but with proper renderings of
Markdown, code, YAML, JSON and JSONL, images, logs, and many other file types.

Its plugin architecture can add custom web-based rendering for any file type.

Metabrowser is a small Starlette Python server with a rich web interface.
It aims to be the most readable way to view Markdown, using clean typography and
full-featured Markdown rendering via [kpress](https://github.com/jlevy/kpress).

## Why Metabrowser

- **Complete Markdown.** KPress provides careful typography, tables, footnotes, syntax
  highlighting, math, links, images, and print-friendly output.

- **Broad file support.** Render common text and source code formats, logs, images, and
  tree-parsed JSON, JSONL, and YAML. Clean support for YAML frontmatter.

- **Scalable browsing of large file trees.** Unlike a Finder or IDE/VSCode tree, the
  file and recent views keep file ages, file and folder counts, and aggregate disk usage
  visible while you browse.
  And the streaming architecture easily scales to 100,000 files or more in a folder.

- **A fast, framework-free frontend.** Metabrowser ships direct CSS and JavaScript with
  no browser framework, keeping rendering quick and customization straightforward.

- **Custom rendering for arbitrary file types.** A compact manifest-based plugin
  architecture adds file matching and browser views, with optional Python data hooks and
  JSONL adapters, without changing Metabrowser core.

## Quick Start

Metabrowser uses [uv](https://docs.astral.sh/uv/). Run the latest published release
without installing a global tool:

```shell
uvx metabrowser ./path/to/artifacts
```

For a reproducible run, pin the release:

```shell
uvx metabrowser@0.1.0 ./path/to/artifacts
```

To make Metabrowser available everywhere as `metab`:

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

> [!WARNING]
> Metabrowser is not a secure, public-facing web server.
> It is a local tool for trusted users browsing files locally or via trusted channels
> like ssh. Treat it with the same level of trust you would a shell or OS file manager.
> Use the default `127.0.0.1` binding, load only trusted plugins, and never expose
> Metabrowser directly to the internet.

## What Metabrowser Opens

Built-in plugins provide views for:

- Markdown rendered by KPress, alongside the source.
- JSON, YAML, and other structured documents.
- Coding-agent JSONL logs and generic JSONL streams.
- Text, source code, images, and binary-file metadata.
- Generic chart summaries for supported agent logs.

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
port is occupied.
Do not change `--host` to expose a served root to an untrusted network;
see the [security policy](SECURITY.md).

## Plugins

Metabrowser is designed to be extended.
A plugin can add:

- File-kind matching rules.
- Browser preview tabs implemented in JavaScript.
- Optional Python data hooks for installed plugin packages.
- JSONL event adapters for additional log formats.

Inspect the complete registry and validate every discovered plugin from the CLI:

```shell
metab plugins list
metab plugins list --json
metab plugins show markdown
metab plugins doctor
```

Metabrowser loads plugins only from trusted sources:

1. built-ins shipped in the Metabrowser wheel
2. installed Python packages registered in the `metabrowser.plugins` entry-point group
3. directories explicitly named with `--plugins-dir` or `METABROWSER_PLUGINS_DIRS`

An installed Python plugin must be present in the same uv tool or uvx environment as
Metabrowser. Operator-directory plugins are useful for local JavaScript-only extensions.

For example, load an operator-reviewed plugin directory with:

```shell
metab serve ./path/to/artifacts --plugins-dir ./trusted-plugins
```

The served data tree is never an implicit plugin source.
See the [plugin authoring guide](docs/plugins.md) for the manifest schema, browser SDK,
packaging, lifecycle rules, and security boundary.

## Use With Coding Agents

Metabrowser includes a portable [Agent Skill](skills/metabrowser/SKILL.md).
Install it for supported coding agents with:

```shell
npx skills add jlevy/metabrowser --skill metabrowser
```

The skill requires no persistent Metabrowser installation.
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
- [Development](docs/development.md)
- [End-to-end testing](docs/e2e-testing.md)
- [Real-time debugging](docs/realtime-debugging.md)
- [Publishing](docs/publishing.md)
- [Security policy](SECURITY.md)
- [Roadmap](TODO.md)

## License

Metabrowser is available under the [MIT License](LICENSE).

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
