# Installation

Metabrowser requires Python 3.12 or newer and is distributed through PyPI.

## Install uv

Install uv with the
[official installation instructions](https://docs.astral.sh/uv/getting-started/installation/).
On macOS, Homebrew is also supported:

```shell
brew install uv
```

Install a supported Python when needed:

```shell
uv python install 3.12
```

## Run Metabrowser

For a one-shot run of the latest published release:

```shell
uvx metabrowser@latest ./path/to/directory
```

Pin the release for a reproducible local, CI, or agent run:

```shell
uvx metabrowser@0.4.0 ./path/to/directory
```

For a persistent global tool installation:

```shell
uv tool install metabrowser
metab ./path/to/directory
```

`metab` is the standard installed command.
The `metabrowser` compatibility command matches the package name and enables the concise
`uvx metabrowser@latest ...` form.

Upgrade deliberately to a reviewed release by naming its exact version:

```shell
uv tool install --upgrade metabrowser==0.4.0
```

Metabrowser installs `kpress==0.3.2` as a required dependency.
Do not install a second KPress checkout beside the package or override it with a
workspace source.

## Run a Source Checkout

Before a version is published, or when developing locally, run the checked-out source
against its exact locks:

```shell
make install
uv --config-file uv.toml run --frozen metab ./path/to/directory
```

The explicit repository config prevents a machine-global uv policy from changing the
lock, and `--frozen` prevents the run command from resolving dependencies.

## Install the Agent Skill

The repository publishes a portable Metabrowser skill for coding agents:

```shell
npx skills add jlevy/metabrowser --skill metabrowser
```

That shorthand follows the installer’s own repository defaults, which suits interactive
use.
Automation should instead pin the installer version and a source tag, reviewed under
[supply-chain policy](../SUPPLY-CHAIN-SECURITY.md) like any other dependency.

Installing the skill does not install Metabrowser itself.
The skill prefers a local `metab` and otherwise falls back to `uvx metabrowser@latest`,
so it needs no persistent Metabrowser installation.
It routes agents to `--help` for current command details and documents the plugin trust
boundary.

The skill deliberately carries no version pin, so it does not go stale between releases.
Enforce the release cool-off with uv configuration instead: set `exclude-newer` in the
uv config that governs the agent’s environment, or `UV_EXCLUDE_NEWER` in the environment
itself, as [supply-chain policy](../SUPPLY-CHAIN-SECURITY.md) requires.
That setting is read from the operator’s uv configuration, not from this repository, so
it has to be configured wherever the agent runs.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
