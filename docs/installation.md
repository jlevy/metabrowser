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
uvx metabrowser@latest ./path/to/artifacts
```

Pin the release for a reproducible local, CI, or agent run:

```shell
uvx metabrowser@0.2.0 ./path/to/artifacts
```

For a persistent global tool installation:

```shell
uv tool install metabrowser
metab ./path/to/artifacts
```

`metab` is the standard installed command.
The `metabrowser` compatibility command matches the package name and enables the concise
`uvx metabrowser@latest ...` form.

Upgrade deliberately to a reviewed release by naming its exact version:

```shell
uv tool install --upgrade metabrowser==0.2.0
```

Metabrowser installs `kpress==0.3.0` as a required dependency.
Do not install a second KPress checkout beside the package or override it with a
workspace source.

## Run a Source Checkout

Before a version is published, or when developing locally, run the checked-out source
against its exact locks:

```shell
make install
uv --config-file uv.toml run --frozen metab ./path/to/artifacts
```

The explicit repository config prevents a machine-global uv policy from changing the
lock, and `--frozen` prevents the run command from resolving dependencies.

## Install the Agent Skill

The repository publishes a portable Metabrowser skill for coding agents:

```shell
npx skills add jlevy/metabrowser --skill metabrowser
```

That shorthand follows the installer’s own repository defaults, which is convenient for
interactive use but not reproducible.
Automation should pin both the installer and the source revision:

```shell
npx --yes skills@1.5.19 add \
  https://github.com/jlevy/metabrowser/tree/v0.2.0/skills/metabrowser \
  --skill metabrowser --yes
```

The two pins solve different problems: the installer pin fixes the code that runs, and
the tag pin fixes the skill content that lands.
Review both under [supply-chain policy](../SUPPLY-CHAIN-SECURITY.md) before changing
them; the installer pin is subject to the same 14-day cool-off as any other npm
dependency.

Installing the skill does not install Metabrowser itself.
The skill prefers a local `metab` and otherwise falls back to the pinned
`uvx metabrowser@0.2.0 ...` runner, so it needs no persistent Metabrowser installation.
It routes agents to `--help` for current command details and documents the plugin trust
boundary.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
