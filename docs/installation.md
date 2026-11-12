# Installation

Metabrowser requires Python 3.12 or newer and is distributed through PyPI.

## Install uv

Install uv with the
[official installation instructions](https://docs.astral.sh/uv/getting-started/installation/);
on macOS and Linux that is the standalone installer:

```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
```

On macOS, Homebrew is also supported:

```shell
brew install uv
```

By default the standalone installer puts uv in `~/.local/bin`, the directory where
`uv tool install` puts commands such as `metab`, and adds it to your shell’s `PATH` for
new terminals. Homebrew does neither: after `brew install uv` and `uv tool install`, run
`uv tool update-shell` once and open a new terminal, or the shell does not find `metab`.

Install a supported Python when needed:

```shell
uv python install 3.12
```

## Run Metabrowser

For a one-shot run of the latest published release:

```shell
uvx metabrowser@latest ./path/to/directory
```

Pin the release for a reproducible local, CI, or agent run, naming the version you
reviewed:

```shell
uvx metabrowser@<version> ./path/to/directory
```

For a persistent global tool installation:

```shell
uv tool install metabrowser
metab ./path/to/directory
```

`metab` is the standard installed command.
The `metabrowser` package-name alias enables the concise `uvx metabrowser@latest ...`
form.

Upgrade deliberately to a reviewed release by naming its exact version:

```shell
uv tool install --upgrade metabrowser==<version>
```

Released versions are on [PyPI](https://pypi.org/project/metabrowser/);
`metab --version` reports the one you have.

Metabrowser installs KPress as a required dependency, at the exact version recorded in
`pyproject.toml` and `uv.lock`. Do not install a second KPress checkout beside the
package or override it with a workspace source.

## The macOS App

The native macOS app is an alpha preview: a development build that you build from
source, not yet a signed or notarized release, and it may change.
It is a thin shell over `metab`: it finds your `metab`, starts one server per folder you
open, and shows each folder in its own window.
It installs nothing itself.
[apps/macos/README.md](../apps/macos/README.md) describes how it works.

It needs:

- macOS 26 or later on Apple silicon;
- Xcode 26 with Swift 6.3 or later, to build it;
- `metab` 0.12.1 or later, which the app finds and runs.

0.12.1 is not yet on PyPI, so for now the `metab` comes from a source checkout.
From the repository root:

```shell
make install
make macos-app
```

`make macos-app` prints where it put the app; open it from there, or build and open a
folder in one step with `make macos-run FOLDER=path/to/folder`. In Settings, Choose
metab… points the app at this checkout’s `.venv/bin/metab`.

Once 0.12.1 is published, the standard setup is the CLI first,
`uv tool install metabrowser`, and then the app.
The app finds `metab` in uv’s tool directory, `~/.local/bin`, without needing it on
`PATH`, so `uv tool update-shell` is only for your terminal.

### What the App Shows Without a Usable metab

If the app finds no `metab` it accepts, Settings opens and lists only the steps still
missing, each with a Copy button:

- without uv, uv’s standalone installer (and `brew install uv` when Homebrew is
  installed), then `uv tool install metabrowser` in a new terminal;
- with uv, `uv tool install metabrowser`;
- with a broken install in uv’s tool directory,
  `uv tool install --reinstall metabrowser`.

The app keeps watching for `metab`, and when it appears, opens the folders you asked for
by itself.

If the `metab` it finds is older than 0.12.1, the app starts no server and shows the
version it found and the command to upgrade:

```shell
uv tool install --upgrade 'metabrowser>=0.12.1'
```

That names a minimum rather than an exact version, so a later `uv tool upgrade` can move
past it. If `metab` is upgraded while the app runs, the app notices the new version and
offers to restart the servers it started from the old one.
An upgrade run in a terminal reaches those servers before the app notices, so restart
them when it asks.

### Disk Images and the Homebrew Cask

The repository’s release pipeline builds a disk image and a Homebrew cask, but nothing
has been released, so neither is available to download yet.
A disk image you build yourself (`make macos-dmg`) is signed only for the Mac that built
it.

Drag the app from a disk image to Applications and open it from there.
A copy opened from the disk image, or from the folder it was downloaded to, runs from a
read-only location and cannot be updated; the app says so when it starts and offers to
show it in Finder, and moving it is up to you.

## Git and GitHub Setup

Git and GitHub CLI (`gh`) are separate tools; installing Metabrowser does not install
them. Choose the tools for what you want to read:

| What you want to do | Extra tools |
| --- | --- |
| Browse local files | None |
| Read Git history or comparisons | Git |
| Open or refresh a public repository URL | Git; cloning works anonymously |
| Fetch a GitHub PR catalog, description, or conversation for an opened repository | `gh`, signed in to github.com |
| Open or refresh a private GitHub repository | Git and `gh`, signed in with access to it |

Repository and PR caching currently require macOS or Linux and a filesystem that
preserves Unix ownership and permissions.
Native Windows caching is not supported.
Ordinary local file browsing does not use this cache.

Cached PR metadata remains readable without `gh`; reading cached Git objects still needs
Git. No Node.js, npm, or separate database service is needed to run Metabrowser.

On macOS with Homebrew, install the missing tools:

```shell
brew install git gh
```

For other platforms, follow the official
[Git installation instructions](https://git-scm.com/install/) and
[GitHub CLI installation instructions](https://github.com/cli/cli#installation).
Use current maintained releases.
Metabrowser refuses acquisition or fetching with Git below its security floor and
reports the versions it accepts.

Check the tools and the active GitHub account in the terminal that will run `metab`:

```shell
git --version
gh --version
gh auth status --active --hostname github.com
```

If `gh` reports that you are not signed in, run:

```shell
gh auth login --hostname github.com
```

Then repeat `gh auth status --active --hostname github.com`. A working saved login is
sufficient; you do not need to set `GH_TOKEN`. For headless use, `gh` also accepts an
[environment token](https://cli.github.com/manual/gh_help_environment). Metabrowser uses
`gh` for GitHub credentials and does not ask you to paste a token into its
configuration. A private repository also requires access for that account.

If a command is not found, install that tool or make its executable available on `PATH`
in the terminal that starts Metabrowser.
If `metab` alone is missing after a successful `uv tool install`, run
`uv tool update-shell` and open a new terminal.
If `gh auth status` reports a connection failure, restore connectivity before trying
again. Installation and sign-in do not fix a network failure.

Native GitHub stack labels are optional.
To enable them, install GitHub’s
[gh-stack extension](https://github.com/github/gh-stack):

```shell
gh extension install github/gh-stack
gh stack --version
```

Metabrowser reads repository stack metadata without changing local stack tracking or
GitHub. If the extension or API is unavailable, PR browsing still works and stack labels
are omitted unless a matching cached snapshot is available.

See [reviewing pull requests](reviewing-pull-requests.md) for comparisons, cached reads,
and refreshing after setup.

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
