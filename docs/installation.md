# Installation

Metabrowser is the Python package `metabrowser`, and `metab` is its command.
uv installs and runs it.
The native macOS app and the agent skill are optional; each runs a `metab` you install
here.

## Release Status

- **`metab`:** these guides describe the code on `main`. The newest release on
  [PyPI](https://pypi.org/project/metabrowser/) can trail it: the Unreleased section of
  the [changelog](../CHANGELOG.md) lists what `main` has that the release lacks, and
  `metab --version` names the version you have.
- **The macOS app:** an alpha preview that you build from source.
  Its release pipeline builds a disk image and a Homebrew cask but has published
  neither, so there is no signed, notarized download.
- **The `metab` the app runs:** the app needs a `metab` at least as new as
  `MetabRequirement.minimum` in `apps/macos/Sources/ShellCore/Setup/MetabVersion.swift`,
  and no release on PyPI meets it yet (`MetabRequirement.isReleased` in the same file
  changes with the release that does).
  Until then the app runs the `metab` of a source checkout, as
  [The macOS App](#the-macos-app) describes.

## Install uv

Install uv with its
[official installation instructions](https://docs.astral.sh/uv/getting-started/installation/).
On macOS and Linux that is the standalone installer:

```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
```

On macOS, Homebrew works too:

```shell
brew install uv
```

The standalone installer puts uv in `~/.local/bin`, where `uv tool install` puts `metab`
too, and adds that directory to your shell’s `PATH` for new terminals.
Homebrew does neither: after `brew install uv` and `uv tool install`, run
`uv tool update-shell` once and open a new terminal, or the shell does not find `metab`.

By default uv downloads a Python in the range that `requires-python` in `pyproject.toml`
names when the machine has none.

## Install metab

Run the latest release once, without installing anything:

```shell
uvx metabrowser@latest ./path/to/directory
```

For a reproducible local, CI, or agent run, name the release you reviewed:

```shell
uvx metabrowser@<version> ./path/to/directory
```

Install `metab` as a tool for everyday use:

```shell
uv tool install metabrowser
metab ./path/to/directory
```

The package installs the command under two names, `metab` and `metabrowser`; the second
is what makes `uvx metabrowser@latest` work.
To upgrade, name the reviewed release:

```shell
uv tool install --upgrade metabrowser==<version>
```

Metabrowser installs KPress, its Markdown renderer, at the exact version that
`pyproject.toml` and `uv.lock` record.
Do not install a second KPress beside it or override it with a workspace source.
No Node.js, npm, or database is needed to run Metabrowser.

To run the code on `main` before it is released, use a source checkout:
[Development](development.md#set-up) has the setup, and then

```shell
make install
uv --config-file uv.toml run --frozen metab ./path/to/directory
```

## Git and GitHub Setup

Git and the GitHub CLI (`gh`) are separate tools; installing Metabrowser installs
neither.

| What you want to do | Extra tools |
| --- | --- |
| Browse local files | None |
| Read commits and diffs | Git |
| Open a public repository URL | Git; cloning is anonymous |
| Fetch a repository’s pull requests | `gh`, signed in to github.com |
| Open a private GitHub repository | Git and `gh`, signed in with access to it |

On macOS with Homebrew:

```shell
brew install git gh
```

Elsewhere, follow the [Git](https://git-scm.com/install/) and
[GitHub CLI](https://github.com/cli/cli#installation) instructions.
Metabrowser refuses to clone or fetch with a Git below its security floor
(`ACQUISITION_MINIMUM` and `ACQUISITION_PATCHED_TRACKS` in
`src/metabrowser/git/process.py`) and names the versions it accepts.

Check the tools and the signed-in account in the terminal that runs `metab`:

```shell
git --version
gh --version
gh auth status --active --hostname github.com
```

If `gh` says you are not signed in, run `gh auth login --hostname github.com` and check
again. A saved login is enough; for headless use `gh` also reads an
[environment token](https://cli.github.com/manual/gh_help_environment). Metabrowser
takes GitHub credentials only from `gh` and never asks for a token itself.

If a command is not found, install it or put it on `PATH` in the terminal that starts
Metabrowser.
If `gh auth status` reports a connection failure, restore the network first;
signing in again does not fix it.

Cached repositories and pull requests need macOS or Linux and a filesystem that keeps
Unix ownership and permissions; native Windows is not supported.
Browsing local files does not use this cache.
Cached pull-request records stay readable without `gh`; cached Git objects still need
Git.

Stack labels for pull requests are optional and come from GitHub’s
[gh-stack extension](https://github.com/github/gh-stack):

```shell
gh extension install github/gh-stack
gh stack --version
```

Metabrowser only reads stack metadata.
Without the extension, pull requests still open and show no stack labels.
[Reviewing pull requests](reviewing-pull-requests.md) covers what these tools enable.

## The macOS App

The app is a native shell over `metab`: it finds your `metab`, starts one server per
folder you open, and shows each folder in its own window.
It installs nothing itself.
[The macOS app guide](macos-app.md) describes using it.

To build it you need:

- an Apple silicon Mac (the default `ARCHES` in `apps/macos/scripts/build-app.sh`) on
  the macOS release that `LSMinimumSystemVersion` in `apps/macos/Resources/Info.plist`
  names;
- the Xcode that provides the Swift tools version `apps/macos/Package.swift` declares;
- a source checkout of this repository, set up as [Development](development.md#set-up)
  describes.

From the repository root:

```shell
make install
make macos-app
```

`make macos-app` prints where it put the app; open it from there, or build and open a
folder in one step with `make macos-run FOLDER=path/to/folder`. While no release meets
the app’s minimum ([Release Status](#release-status)), point the app at the checkout’s
`metab`: Settings > Choose metab… and the checkout’s `.venv/bin/metab`.

Once a release meets it, install the CLI first with `uv tool install metabrowser`, then
open the app. The app finds `metab` in uv’s tool directory without needing it on `PATH`,
so `uv tool update-shell` is only for your terminal.
Without a `metab` it can run, the app lists the steps still missing
([what the app shows](macos-app.md#what-the-app-shows-without-a-usable-metab)).

The app has no updater: rebuild it from a newer checkout.
Upgrading `metab` is separate, and the app offers to restart its servers when it notices
([Choosing a metab](macos-app.md#choosing-a-metab)).

A disk image you build yourself (`make macos-dmg`) is signed only for the Mac that built
it. Drag the app from an image to Applications and open it from there.
[apps/macos/README.md](../apps/macos/README.md) has the build, test, and release
details.

## The Agent Skill

The repository publishes a Metabrowser skill for coding agents:

```shell
npx skills add jlevy/metabrowser --skill metabrowser
```

That shorthand follows the installer’s own defaults, which suits interactive use.
Automation should pin the installer version and a source tag, reviewed under the
[supply-chain policy](../SUPPLY-CHAIN-SECURITY.md) like any other dependency.

The skill installs no Metabrowser: it runs a local `metab` when there is one and
otherwise `uvx metabrowser@latest`. It carries no version pin, so it does not go stale
between releases. Enforce the release cool-off in uv configuration instead, wherever the
agent runs: set `exclude-newer` in the uv configuration of the agent’s environment, or
`UV_EXCLUDE_NEWER` in that environment, as the
[supply-chain policy](../SUPPLY-CHAIN-SECURITY.md) requires.
[Working with agents](working-with-agents.md) describes what the skill does.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
