# Installation

MetaBrowser requires Python 3.12 or newer and is distributed through PyPI.

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

## Run MetaBrowser

For a one-shot run in an isolated environment:

```shell
uvx --from metabrowser==0.1.0 metabrowser ./path/to/artifacts
```

For a persistent command installation:

```shell
uv tool install metabrowser==0.1.0
metabrowser ./path/to/artifacts
```

Upgrade deliberately to a reviewed release by naming its exact version:

```shell
uv tool install --upgrade metabrowser==0.1.1
```

MetaBrowser installs `kpress==0.2.0` as a required dependency.
Do not install a second KPress checkout beside the package or override it with a
workspace source.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
