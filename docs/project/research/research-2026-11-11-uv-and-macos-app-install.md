# Research: Installing the Native macOS App Through uv and `metab`

**Date:** 2026-11-11

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Complete

Extends [Native macOS App for Metabrowser](research-2026-11-08-macos-app-packaging.md)
(2026-11-08), which settles the shell, the uv runtimes, CLI layering, signing,
notarization, the Homebrew cask, and Sparkle, and
[Server Topology, Lifecycle, and Agent Handoff](research-2026-11-10-native-app-server-topology.md)
(2026-11-10). Neither asks whether uv, which already installs `metab`, can also install
or launch the app.

## Overview

`metab` installs with `uv tool install metabrowser`, and `uvx metabrowser` runs it
without installing. The native app is a thin AppKit and `WKWebView` shell over that CLI,
planned as a Developer ID–signed, notarized DMG on GitHub Releases plus a Homebrew cask.
The question here: has anyone used uv, uvx, or pipx to install, update, or launch a
native `.app`, in a way that leaves a normal app in `/Applications` or `~/Applications`,
discoverable and usable like any other?
And which macOS behaviors decide whether a design like that works?

The facts that frame it: the app finds a CLI install in `~/.local/bin`, uv’s tool
directory, Homebrew, or the login shell’s `PATH`, and starts one `metab` server per
folder; dev and release variants have separate bundle ids
(`io.github.jlevy.metabrowser.dev` and `io.github.jlevy.metabrowser`); and `metab` stays
the product.

## Summary

- **Nobody uses uv itself to install a Mac app, and uv and pipx have scoped it out.**
  pipx closed its desktop-integration request as out of scope; uv’s one related request
  (icons) is open and unplanned, and its maintainers oppose install-time hooks.
  Wheels cannot run code at install time or place files outside the environment.
- **The pattern exists one level up, in a package’s own CLI.** Photini, pyhidra,
  desktop-app, and rfswarm ship a subcommand that writes a launcher `.app` into
  `~/Applications` or `/Applications`; conda’s menuinst and `pixi global install` do it
  from the package manager; Claude Code writes a URL-handler app into `~/Applications`
  on use. All of these generate an unsigned or ad hoc launcher around a script.
  The closest precedents for installing a real, notarized app from a command line are
  kitty’s and Zed’s `curl | sh` installers, which verify nothing, and Homebrew’s cask,
  which checks a hash and leaves Gatekeeper to check the rest.
- **Recommendation: the CLI installs the app (design a).** A `metab` mode fetches the
  notarized, stapled ZIP from GitHub Releases, verifies it with base-OS tools against
  the project’s Developer ID Team ID and Apple’s notarization, and moves a complete copy
  into `/Applications` (or `~/Applications` when the user cannot write there).
  Then `uvx metabrowser <install mode>` gets any uv user the real app in one command,
  and `uv tool install metabrowser` gives that app a CLI to run.
- **Skipping quarantine is a trade, not a bypass.** A CLI download carries no
  `com.apple.quarantine` (measured for `curl` and uv), so the user sees no “downloaded
  from the Internet” prompt and the app is never translocated, which also keeps Sparkle
  working. macOS 13 and later still check a notarized app’s integrity on first launch,
  but the installer has to do the identity checks Gatekeeper would otherwise do.
  Measured here: about 0.5–0.9 s per check.
- **Copy the real app and replace it whole.** Symlinked apps are invisible to Spotlight,
  which is why Homebrew dropped `brew linkapps` and nix-darwin switched to copies.
  Apple’s app bundle protection blocks other teams’ processes, Terminal included, from
  writing inside an app that has been launched, so an update stages a full new copy and
  renames it into place.
- **A wheel that carries the app (b) and a generated launcher (c) both fail.** A signed
  bundle survived a uv wheel install only while it held no symlinks; one symlink broke
  its seal (measured), and Sparkle’s framework needs them.
  A generated launcher is not the Swift shell, and an ad hoc one gets a new code
  identity, and loses its privacy grants, each time it is regenerated.
- **Finding each other needs two fixes.** The app cannot find a `metab` that ran only
  through `uvx`, because that environment lives in uv’s disposable cache.
  And `metab` must find the app by bundle id through LaunchServices and filter the
  result: on this Mac, LaunchServices returned two release-variant rehearsal builds
  inside repository checkouts and no copy in an Applications folder.
- **One owner updates each copy:** Homebrew for a cask install, `metab` for its own, and
  Sparkle for both once it ships, with the cask declaring `auto_updates true`.

## Questions to Answer

1. Has anyone used uv, uvx, or pipx to install, update, or launch a native `.app`?
2. Which designs are plausible, and what does each cost?
3. Which macOS behaviors (quarantine, Gatekeeper, translocation, signing,
   LaunchServices, app bundle protection) decide whether they work?
4. How do the app and a uv-installed `metab` find and update each other?
5. How does a design fit the repository’s CLI parity and supply-chain rules?

## Scope

**In scope:** arm64 Macs on macOS 15 and later; both variants; installing, updating,
launching, and removing the app from a command line; how that interacts with the cask,
Sparkle, and the earlier brief’s app-managed runtime; Linux and Windows desktop entries
only as analogues.

**Out of scope:** the shell, the runtime builder, signing, and notarization themselves
(the 2026-11-08 brief); server topology and the agent front door (the 2026-11-10 brief);
the Mac App Store.

## Terms

- **Install channel:** how a copy of the app reaches an Applications folder: a DMG drag,
  the cask, a `metab` install, or (later) a Sparkle update.
- **Owner:** the channel that updates a given copy.
- **Quarantine:** the `com.apple.quarantine` extended attribute that makes Gatekeeper
  assess a file when it is first opened.
  **Provenance** is `com.apple.provenance`, an attribute macOS 13 and later attach to
  files that apps write.
- **App Translocation:** Gatekeeper running a quarantined app from a randomized
  read-only path.
- **Designated requirement (DR):** the code-signing rule that says which later builds
  count as the same program; privacy (TCC) grants are recorded against it.
- **App bundle protection:** Apple’s macOS 13 “app management” rule that blocks
  modifying an app’s bundle unless the modifier is signed by the same team or allowed by
  the app’s `NSUpdateSecurityPolicy`.

## Findings

### Prior Art

Sources were read at pinned tags or commits on 2026-11-11; every row is verified unless
marked otherwise.

**Python package installers decline the job.**

- **uv:** [uv#13729](https://github.com/astral-sh/uv/issues/13729) (“`uv tool` should
  support icons”, open since 2025-05-30) is the only request near desktop integration;
  searches for `.desktop` files, Start-menu entries, app bundles, and Applications found
  nothing else. [uv#12750](https://github.com/astral-sh/uv/issues/12750) asks for
  commands to run after a package installs; maintainers are opposed, citing post-install
  scripts used for credential theft.
  `gui-scripts` differ from console scripts only on Windows
  ([config docs](https://github.com/astral-sh/uv/blob/0.13.7/docs/concepts/projects/config.md),
  [wheel.rs](https://github.com/astral-sh/uv/blob/0.13.7/crates/uv-install-wheel/src/wheel.rs#L178-L196)),
  and `uv tool install` exposes only the wheel’s scripts
  ([uv-tool](https://github.com/astral-sh/uv/blob/0.13.7/crates/uv-tool/src/lib.rs#L414-L466)).
- **pipx:** [pipx#717](https://github.com/pypa/pipx/issues/717) (desktop integration on
  Linux) was closed as out of scope in 2023, after a maintainer said Python packaging
  does not handle desktop integration;
  [pipx#416](https://github.com/pypa/pipx/issues/416) (data files outside the
  environment) was declined, and the
  [scope document](https://github.com/pypa/pipx/blob/1.18.16/docs/explanation/scope.rst)
  limits pipx to environments and entry points.
- **The wheel format:** the
  [binary distribution format](https://packaging.python.org/en/latest/specifications/binary-distribution-format/)
  defines no install hooks, and wheels cannot hold symlinks; the proposal to add them,
  [PEP 778](https://peps.python.org/pep-0778/), is deferred.
  A [2021 Discourse thread](https://discuss.python.org/t/7853) ended against wheels
  installing outside their environment.

**Another package manager does it.**

- **conda’s menuinst v2** writes a real `<name>.app` into `~/Applications` (user mode)
  or `/Applications` (system mode), with a small compiled launcher that runs a shell
  script, an `Info.plist` built from a JSON menu file, and an ad hoc signature only when
  the menu declares entitlements
  ([osx.py](https://github.com/conda/menuinst/blob/2.5.2/menuinst/platforms/osx.py)).
  napari and Spyder use it for their conda installers.
- **`pixi global install`** creates menuinst shortcuts by default, in user mode
  ([manifest docs](https://github.com/prefix-dev/pixi/blob/v0.84.2/docs/global_tools/manifest.md)).
  It is the nearest thing to a tool installer that places apps.

**Packages do it themselves, from their own CLI.**

| Package | Command | What it writes | Signing |
| --- | --- | --- | --- |
| [Photini](https://github.com/jim-easterbrook/Photini/blob/91294af071ad8387bc746ee3ec773589710efdd4/src/photini/macos.py) | `photini-post-install`, with `--remove` | `~/Applications/Photini.app` (`/Applications` as root): the gui-script as the executable and a `plistlib`-written `Info.plist`; the same command writes a `.desktop` file on Linux and Start-menu shortcuts on Windows | none |
| [pyhidra](https://github.com/dod-cyber-crime-center/pyhidra/blob/1b3773ab30d1a1fa1a70725d8831d50a708e942e/pyhidra/mac_shortcut.py) | `python -m pyhidra.install_desktop` | a script hard-coding `sys.executable`, tied to that environment | a hand-written `CodeResources`, not a signature |
| [desktop-app](https://github.com/chrisjbillington/desktop-app/blob/f4c2741639253ecfcf766f6fe02efb39e991552e/desktop_app/macos.py) | `desktop-app install <module>` | `~/Applications/<name>.app` with a shell launcher (since 2026-05) | none |
| [rfswarm](https://github.com/damies13/rfswarm/blob/9147304ab3e8abf4471ae83e1f8e25bf0088fda1/rfswarm_manager/rfswarm.py#L971-L1085) | `rfswarm -c ICON` | `/Applications` if writable, else `~/Applications`; the executable is a symlink to the console script | none |
| [pyshortcuts](https://github.com/newville/pyshortcuts/blob/1.9.12/pyshortcuts/darwin.py) | a library call | an Automator-stub app on the Desktop, optionally in `/Applications` | ad hoc, for a stable privacy identity (its comment) |
| [dwex](https://github.com/sevaa/dwex/blob/1c2a8607c48d3b57032246014255d26f8e42b206/setup.py#L53-L131) | `pip install` (a `setup.py` install override) | `/Applications/DWARF Explorer.app` | none; under PEP 517 builds the hook most likely runs at wheel build time (inferred) |

**A command-line tool that writes an app on use:** Claude Code registers its
`claude-cli://` scheme by writing `~/Applications/Claude Code URL Handler.app` on macOS,
a `.desktop` file on Linux, and a registry key on Windows, with no separate install
command ([deep links](https://code.claude.com/docs/en/deep-links)). On this Mac the
bundle holds only an `Info.plist` and an executable that is a symlink to the CLI in
`~/.local/bin` (observed; see Measurements).
A related bug: its `/desktop` command looked for the desktop app only in `/Applications`
and missed a copy in `~/Applications`
([claude-code#41899](https://github.com/anthropics/claude-code/issues/41899)).

**Script installers that place a real, notarized app.**

- **kitty:** `installer.sh` downloads the DMG with `curl`, mounts it, `ditto`s
  `kitty.app` into `/Applications` after `rm -rf` of the old copy, and launches it with
  `open`. It checks no hash or signature and does nothing about quarantine; updating
  means running it again
  ([installer.sh](https://github.com/kovidgoyal/kitty/blob/v0.50.0/docs/installer.sh)).
  It comments that `hdiutil` is deprecated on macOS 27 and uses `diskutil image attach`
  there (not confirmed in Apple’s release notes).
- **Zed:** `install.sh` does the same into a hard-coded `/Applications` and links the
  CLI as `~/.local/bin/zed`, again with no checks
  ([install.sh](https://github.com/zed-industries/zed/blob/v1.27.0/script/install.sh#L153-L171)).
  Zed’s updater later `rsync`s a new DMG into the running bundle in place, checking only
  the HTTP status
  ([auto_update.rs](https://github.com/zed-industries/zed/blob/v1.27.0/crates/auto_update/src/auto_update.rs#L1076-L1245)).

**Apps that install their CLI (the reverse direction).**

- **VS Code** links `/usr/local/bin/code` through `osascript` with administrator
  privileges, always prompting
  ([source](https://github.com/microsoft/vscode/blob/1.146.0/src/vs/platform/native/electron-main/nativeHostMainService.ts#L551-L640)),
  and `code` finds its app by resolving its own path up to the `.app`
  ([code.sh](https://github.com/microsoft/vscode/blob/1.146.0/resources/darwin/bin/code.sh)).
  Zed’s in-app installer tries `/usr/local/bin` unprivileged first
  ([install_cli](https://github.com/zed-industries/zed/blob/v1.27.0/crates/install_cli/src/install_cli_binary.rs)),
  and JupyterLab Desktop links `/usr/local/bin/jlab` at first launch
  ([utils.ts](https://github.com/jupyterlab/jupyterlab-desktop/blob/v4.6.3-1/src/main/utils.ts)).
- **Ollama** offers to move itself into `/Applications` and links
  `/usr/local/bin/ollama` with an admin prompt
  ([app_darwin.m](https://github.com/ollama/ollama/blob/v0.40.16/app/cmd/app/app_darwin.m#L1979-L2215));
  its updater checks that the new bundle’s signature is valid but pins no Team ID
  ([updater](https://github.com/ollama/ollama/blob/v0.40.16/app/updater/updater_darwin.go)).
- **LM Studio** is the closest analogue to a separately installed CLI: `lms bootstrap`
  appends its directory to the user’s shell startup files
  ([bootstrap.ts](https://github.com/lmstudio-ai/lms/blob/138dcffbc40e5fe3d9c0d38cf75dcdc1d883d849/src/subcommands/bootstrap.ts)),
  and the CLI starts the app from a location file the app writes, not by searching
  ([localAPIServer.ts](https://github.com/lmstudio-ai/lms/blob/138dcffbc40e5fe3d9c0d38cf75dcdc1d883d849/src/localAPIServer.ts#L105-L150)).
- **Desktop apps that bundle or drive Python** offer no pip or uv path to the app.
  JupyterLab Desktop has no PyPI or conda-forge package of the app, only a DMG;
  Datasette Desktop pip-installs into its own `~/.datasette-app/venv`
  ([main.js](https://github.com/simonw/datasette-app/blob/0.2.3/main.js#L317-L460)); and
  Positron links its CLI as VS Code does
  ([source](https://github.com/posit-dev/positron/blob/2026.11.1-4/src/vs/platform/native/electron-main/nativeHostMainService.ts#L588)).
  marimo has no official desktop app (searched its issues; inferred from absence).

**Package managers that place real apps.**

- **Homebrew casks:** `app` moves the bundle into `appdir` and leaves a symlink in the
  Caskroom; `binary` symlinks a CLI from inside the app into Homebrew’s `bin`;
  `--appdir=~/Applications` is supported
  ([moved.rb](https://github.com/Homebrew/brew/blob/7.0.13/Library/Homebrew/cask/artifact/moved.rb#L155-L185),
  [env_config.rb](https://github.com/Homebrew/brew/blob/7.0.13/Library/Homebrew/env_config.rb#L243)).
  Homebrew checks the cask’s SHA-256, quarantines the download through the public
  quarantine API, and sets bit 0x0100, which its code calls the app translocation bit,
  so Gatekeeper still assesses the app but does not translocate it; on an upgrade with
  an unchanged signer it also sets the user-approved bit 0x0040
  ([quarantine.rb](https://github.com/Homebrew/brew/blob/7.0.13/Library/Homebrew/cask/quarantine.rb#L127-L134)).
  For `auto_updates true` casks, `brew upgrade` now compares the installed bundle’s
  version and skips an app that updated itself
  ([cask.rb](https://github.com/Homebrew/brew/blob/7.0.13/Library/Homebrew/cask/cask.rb#L477-L497)).
- **Symlinks fail:** Homebrew deprecated `brew linkapps` in 2017 because symlinked or
  aliased apps cannot behave with Spotlight
  ([brew#1808](https://github.com/Homebrew/brew/pull/1808)); nix-darwin replaced its
  symlinked `/Applications/Nix Apps` with real copies in 2025
  ([nix-darwin#1396](https://github.com/nix-darwin/nix-darwin/pull/1396)), and
  home-manager added copies into `~/Applications/Home Manager Apps`
  ([home-manager#8031](https://github.com/nix-community/home-manager/pull/8031)).
  MacPorts installs apps into `/Applications/MacPorts`
  ([macports.conf](https://github.com/macports/macports-base/blob/v2.12.7/doc/macports.conf.5)).

**App builders produce bundles but install nothing.**

- **Briefcase** has no install command; its DMG holds an Applications link, and its
  `.pkg` installs to `/Applications` through Installer
  ([commands](https://github.com/beeware/briefcase/blob/v0.4.7/docs/en/reference/commands/index.md),
  [macOS](https://github.com/beeware/briefcase/blob/v0.4.7/src/briefcase/platforms/macOS/__init__.py#L1877-L1882)).
  It documents running itself with `uvx briefcase`
  ([run.md](https://github.com/beeware/briefcase/blob/v0.4.7/docs/en/how-to/run.md)) and
  supports uv as its environment manager since 0.4.5
  ([configuration](https://github.com/beeware/briefcase/blob/v0.4.7/docs/en/reference/configuration.md#L108-L116)):
  uv runs the builder, not the install.
- **py2app** (alias mode builds a `.app` tied to the local Python
  [tutorial](https://github.com/ronaldoussoren/py2app/blob/v0.28.10/doc/tutorial.rst#L30-L54)),
  **PyInstaller**
  ([BUNDLE](https://github.com/pyinstaller/pyinstaller/blob/v6.22.3/doc/spec-files.rst#L433-L463)),
  and **Nuitka**
  ([`--macos-create-app-bundle`](https://github.com/Nuitka/Nuitka/blob/4.3.5/nuitka/options/OptionParsing.py#L1977-L1988))
  build bundles into an output folder.
  Toga, rumps, and pywebview point to these builders and offer no install-from-pip
  launcher
  ([pywebview](https://github.com/r0x0r/pywebview/blob/6.2.1/docs/guide/freezing.md),
  [rumps](https://github.com/jaredks/rumps/blob/d304385711f7d6b81963a800324529d5ae389503/README.rst)).
- **PyApp** can bootstrap with uv (`PYAPP_UV_ENABLED`) but builds a single executable,
  not a `.app`
  ([installation](https://github.com/ofek/pyapp/blob/v0.31.0/docs/config/installation.md)),
  and so does Hatch’s `binary` target, which uses it
  ([binary](https://github.com/pypa/hatch/blob/hatchling-v1.33.0/docs/plugins/builder/binary.md)).
  PyOxidizer’s author called it “effectively in a zombie state” in 2024
  ([post](https://gregoryszorc.com/blog/2024/03/17/my-shifting-open-source-priorities/)).

What this adds up to: no project uses uv or pipx to install a Mac app, and no Python
precedent installs a Developer ID–signed, notarized one.
The Python precedents all generate a launcher around an interpreter, and their bundles
are unsigned or ad hoc.
Installing a prebuilt notarized app from a command line is done only by shell installers
(kitty, Zed), which verify nothing, and by Homebrew, which hands verification to
Gatekeeper.

### Measurements

Run on an arm64 Mac with macOS 26.5.2, uv 0.12.8, and `curl` 8.7.1, in a scratch
directory, with every uv directory redirected there.
Full Xcode is installed on this machine.
Nothing was written to an Applications folder or to the LaunchServices database.

| Probe | Command | Result |
| --- | --- | --- |
| `curl` download | `curl -fsSL -o f <url>; xattr -l f` | `com.apple.provenance` only; no `com.apple.quarantine`. A file made with `touch` in the same shell also got provenance, so provenance marks the writing process, not a download |
| uv-managed Python | `UV_PYTHON_INSTALL_DIR=… UV_CACHE_DIR=… uv --no-config python install 3.14 --no-bin` | 3.14.7 installed in 8.5 s; 0 of 1,693 files quarantined; every file carries provenance; `python3.14` is ad hoc and linker-signed, with a designated requirement of `cdhash H"…"` |
| A signed bundle inside a wheel | two hand-built wheels tagged `py3-none-macosx_15_0_arm64`, each holding an ad hoc–signed bundle, installed by `uv pip install` into a scratch environment | without symlinks: the executable bit survived and `codesign --verify --strict --deep` passed. With one symlink: uv wrote it as an 8-byte regular file and verification failed (“a sealed resource is missing or invalid”). Neither copy was quarantined |
| Tools on a Mac without developer tools | `codesign -dv` on each tool | `codesign`, `spctl`, `syspolicy_check`, `gktool`, `ditto`, `hdiutil`, `diskutil`, and `plutil` are system binaries; `/usr/bin/stapler`, like `/usr/bin/git`, is an `xcode-select` shim, so `stapler validate` needs the developer tools |
| Checks on a notarized third-party app | `codesign --verify --deep --strict`; the same with `-R` pinning its Team ID; `codesign -R=notarized --check-notarization`; `spctl --assess --type execute`; `syspolicy_check distribution` | 0.75, 0.52, 0.77, 0.82, and 0.91 s; all passed, and a wrong Team ID failed the requirement. On the ad hoc test bundle, `--check-notarization` exited 3, `spctl` rejected it, and `syspolicy_check` flagged it as ad hoc |
| `/Applications` permissions | `ls -ld /Applications` | `drwxrwxr-x root admin`: admin-group members can write without `sudo`; standard users cannot |
| Quarantine on installed apps | `xattr -p com.apple.quarantine` on each bundle in `/Applications` | 53 of 151 apps carried it. Apps whose attribute names a browser mostly had `01c1` or `0181`; the two cask-installed apps had `0381` and `03c1`; 49 of the 53 have bit 0x0100 set. The other 98 carried none (App Store and package installs, apps rewritten by their own updaters, and local builds, inferred) |
| LaunchServices lookup | `URLsForApplicationsWithBundleIdentifier` through `osascript -l JavaScript`, read-only | 0.08–0.09 s per query. The dev bundle id resolved to a build directory in a repository checkout, and the release bundle id to two rehearsal builds in two other checkouts; neither id resolved to an Applications folder |
| Spotlight | `mdfind -onlyin /Applications 'kMDItemContentType == "com.apple.application-bundle"'` | nothing, even for `/Applications`; `mdutil -s /` reports indexing disabled on this machine, so whether `~/Applications` is indexed could not be measured here |
| A CLI-generated bundle | `codesign --verify`, `spctl --assess`, and a listing of Claude Code’s URL-handler app | an `Info.plist` and `Contents/MacOS/claude`, a symlink to the CLI; the bundle fails verification (“code has no resources but signature indicates they must be present”) and `spctl` rejects it, yet LaunchServices resolves its bundle id |

### The macOS Behaviors That Decide It

Each claim is verified in Apple documentation or a post by Apple Developer Technical
Support (DTS) unless marked otherwise.

- **Who sets quarantine:** apps that opt in with
  [`LSFileQuarantineEnabled`](https://developer.apple.com/documentation/bundleresources/information-property-list/lsfilequarantineenabled)
  or the
  [quarantine API](https://developer.apple.com/documentation/foundation/urlresourcekey/quarantinepropertieskey),
  and browsers such as Safari.
  `curl` and `scp` do not ([DTS](https://developer.apple.com/forums/thread/706442)), and
  neither does uv (measured).
  Archive Utility propagates quarantine to what it unpacks, while `tar` and `unzip` do
  not (same post); `ditto` preserves it by default and `--noqtn` drops it
  ([ditto(1)](https://keith.github.io/xcode-man-pages/ditto.1.html)). DTS says the
  attribute’s on-disk format is not API.
- **What Gatekeeper checks without quarantine:** running a quarantined app always
  invokes Gatekeeper; otherwise it “typically only kicks in” when the app is quarantined
  ([DTS](https://developer.apple.com/forums/thread/740680)). Since macOS 13 it checks
  the integrity of all notarized apps, quarantined or not, and blocks a notarized app
  whose signature is no longer valid
  ([WWDC22 10096](https://developer.apple.com/videos/play/wwdc2022/10096/)). XProtect
  scans apps at first launch and when they change
  ([Platform Security](https://support.apple.com/guide/security/protecting-against-malware-sec469d47bd8/web)).
  The first-open approval prompt is tied to downloaded, in practice quarantined,
  software (the tie is corroborated only by
  [Eclectic Light](https://eclecticlight.co/2023/07/05/how-does-ventura-check-the-security-of-known-apps-and-command-tools/)).
  So a CLI installer that leaves no quarantine gets no prompt and cannot count on an
  online notarization check; it must check identity itself.
  DTS calls `spctl` a rough check and recommends `syspolicy_check`
  ([DTS](https://developer.apple.com/forums/thread/130560)).
- **When translocation applies:** for zip and disk-image distribution, Gatekeeper
  randomizes the path of an app opened without being moved, on first launch only, and
  not after the user moves it
  ([Packaging Mac software](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution)).
  DTS believes only a Finder move clears it and says this is undocumented
  ([DTS](https://developer.apple.com/forums/thread/732370)), and there is no supported
  API to detect it ([DTS](https://developer.apple.com/forums/thread/724969)). Sparkle
  refuses to update a translocated copy or one on a read-only volume
  ([SPUBasicUpdateDriver.m](https://github.com/sparkle-project/Sparkle/blob/2.10.1/Sparkle/SPUBasicUpdateDriver.m#L71-L80)).
  A copy that was never quarantined is not translocated (corroborated, and implied by
  Homebrew needing bit 0x0100 only because it quarantines).
- **Signing and privacy grants:** on Apple silicon every executable must be signed, and
  an ad hoc signature suffices to run
  ([Big Sur release notes](https://developer.apple.com/documentation/macos-release-notes/macos-big-sur-11_0_1-universal-apps-release-notes)).
  macOS records an app’s designated requirement in the privacy database, and ad hoc
  code’s requirement matches only that exact build
  ([TN3127](https://developer.apple.com/documentation/technotes/tn3127-inside-code-signing-requirements)),
  so each regenerated ad hoc bundle is a new program to TCC
  ([DTS](https://developer.apple.com/forums/thread/678816)). Developer ID builds from
  the same team keep their grants.
- **App bundle protection:** since macOS 13, a modification by a process that is neither
  same-team nor allowed by
  [`NSUpdateSecurityPolicy`](https://developer.apple.com/documentation/bundleresources/information-property-list/nsupdatesecuritypolicy)
  is blocked, and the user is notified (WWDC22 10096). When Terminal could not create
  files inside an already-launched browser’s bundle, DTS advised building a complete new
  copy of the app and moving that into place
  ([DTS](https://developer.apple.com/forums/thread/779326),
  [earlier thread](https://developer.apple.com/forums/thread/761436)). Whether renaming
  or deleting a whole launched bundle from Terminal is also blocked is unsettled;
  Homebrew falls back to uninstall and reinstall when it lacks the permission
  (corroborated by
  [Homebrew’s FAQ](https://github.com/Homebrew/brew/blob/7.0.13/docs/FAQ.md) and
  [Jeff Johnson](https://lapcatsoftware.com/articles/AppManagement.html)).
- **Registration and discoverability:** LaunchServices scans the Applications folders of
  every domain, the user’s included, at boot and login, Finder registers apps it sees,
  and installers should call `LSRegisterURL`
  ([Launch Services concepts](https://developer.apple.com/library/archive/documentation/Carbon/Conceptual/LaunchServicesConcepts/LSCConcepts/LSCConcepts.html),
  archived;
  [LSRegisterURL](https://developer.apple.com/documentation/coreservices/1446350-lsregisterurl)).
  It also registers bundles elsewhere, build folders included (measured).
  `~/Applications` is the standard place for one user’s apps and `/Applications` for all
  users, and the local domain needs administrative privileges to change
  ([File System Programming Guide](https://developer.apple.com/library/archive/documentation/FileManagement/Conceptual/FileSystemProgrammingGuide/FileSystemOverview/FileSystemOverview.html)).
  macOS 26 replaced Launchpad with an Apps view in Spotlight, where non-App Store apps
  appear once dragged to the Applications folder
  ([Mac User Guide](https://support.apple.com/guide/mac-help/mh35840/26.0/mac/26.0));
  whether that view and Spotlight include `~/Applications` is unsettled.
- **Installing by script:** Apple names zip, DMG, and pkg as the direct-distribution
  containers and is silent on command-line installs (Packaging Mac software).
  Its updater guidance is to write a new copy and rename it into place, never modify
  files in place
  ([Updating Mac Software](https://developer.apple.com/documentation/security/updating-mac-software)).

### How the App and `metab` Find Each Other

- **App to CLI:** the spike’s discovery checks the saved path, `METABROWSER_METAB`,
  `~/.local/bin`, uv’s tool bin directory, the Homebrew prefixes, and the login shell’s
  `PATH`. A `uvx` environment is stored in uv’s cache, treated as disposable, and not on
  `PATH`
  ([uv tools](https://github.com/astral-sh/uv/blob/0.13.7/docs/concepts/tools.md)), so
  an app installed by `uvx metabrowser …` finds no CLI unless one is installed
  separately.
- **CLI to app:** nothing finds the app today.
  Fixed paths miss `~/Applications` (claude-code#41899). Spotlight queries need
  indexing, which was off here.
  A LaunchServices query by bundle id works (0.09 s, measured) and returns every
  registered copy, build folders included, so it needs filtering.
  From Python without new dependencies it can run through `ctypes` into CoreServices
  (`LSCopyApplicationURLsForBundleIdentifier`; inferred, not built here).
  LM Studio’s alternative, a location file the app writes, misses copies that have not
  run yet.
- **Versions:** `metab` can read a copy’s `Info.plist` with the standard library’s
  `plistlib`. The earlier brief’s answer for skew between the app and a CLI install
  (VERSION + FAIL FAST on the host-protocol version) applies unchanged.

## Key Insights

- **The question bundles four decisions:** who fetches the app (uv, `metab`, a browser,
  Homebrew), where it lands (an Applications folder or inside the uv environment), who
  verifies it (Gatekeeper through quarantine, or the installer), and who updates it.
- **uv cannot be the installer, but it can be the bootstrap.** Wheels have no hooks and
  cannot place files outside the environment, by design.
  `uvx` already gives any uv user a working `metab` in one command, and that `metab` can
  do the rest: the Photini and menuinst pattern, pointed at a notarized artifact instead
  of a generated launcher.
- **“Native and in Applications” requires a real copy of the real app.** Symlinks fail
  Spotlight, and a generated launcher is not the Swift shell and has no stable identity.
- **Installing without quarantine moves Gatekeeper’s job into the installer.** It also
  removes translocation, the condition under which Sparkle refuses to update.
- **Updating is harder than installing.** Three channels could own a copy, app bundle
  protection limits writes from Terminal, and an update must replace the bundle whole.
- **Installing the CLI first and installing the app first should converge.** “`metab`
  installs the app” and the earlier brief’s “the app builds a runtime and offers a
  command-line launcher” should end in the same state, recorded in one place.

## Options Considered

| Option | What happens | For | Against |
| --- | --- | --- | --- |
| **(a) The CLI installs the app** | a `metab` mode fetches the notarized ZIP, verifies it, and moves a complete copy into an Applications folder | the real signed app; works from `uvx`; base-OS tools only; no admin prompt for admin-group users or into `~/Applications` | the installer must verify identity itself; a new CLI surface with parity work; update ownership to manage |
| **(b) A wheel carries the app** | a macOS-only wheel holds the `.app` as package data; a command copies it out | PyPI and the user’s lock carry integrity; no second download | symlinks break the seal (measured), so Sparkle’s framework cannot ride along; a bigger download for users who never want the app; `/apps/` is kept out of every distribution today; still needs a copy step and an update step |
| **(c) A generated launcher** | `metab` writes a small `.app` that starts the CLI or a browser window | no download; no notarization | uv cannot run it at install; not the Swift shell; ad hoc identity changes on every regeneration, or a symlinked executable fails verification (measured) |
| **(d) The app bootstraps `metab`** (2026-11-08 brief) | the DMG or cask installs the app; a bundled uv builds a hash-pinned runtime | serves users without uv; already planned (`mb-lrcd`) | the app-first direction only; leaves CLI users with two installs |
| **(e) Point the user to the DMG or cask** | `metab` prints the release URL or the `brew` command | no new mechanism | not streamlined; a browser download is quarantined and translocated until moved |

### Option (a) in Detail

**Artifact:** the ZIP of the stapled app, not the DMG. It needs no mounting and no
`hdiutil`, and `ditto -x -k` keeps symlinks, which a later Sparkle framework needs.
The spike’s release pipeline already zips the app with `ditto` for `notarytool`, and the
earlier brief’s Recommendation 6 already ships a DMG and a ZIP.

**Verification:** never set quarantine, verify, then install.

- Download with the standard library over HTTPS, with a size bound, into a private
  staging directory on the destination’s volume.
- Check the release’s SHA-256 asset, which guards against corruption, not tampering.
- Run `codesign --verify --strict --deep` with a requirement that pins the Developer ID
  anchor, the Team ID, and the release bundle id, so the dev variant and anyone else’s
  app are refused.
- Run `codesign -R=notarized --check-notarization`, which needs no developer tools.

The Team ID in `metab`’s reviewed source is the trust anchor: forging an app that passes
would take the project’s signing key and Apple’s notarization.
Pinning the ZIP’s hash in each `metab` release would be stronger, but once the app
bundles a lock for a `metab` version (Phase 5), each release would have to be built
before the other. Setting quarantine on purpose, as Homebrew does, would restore
Gatekeeper’s prompt, but the no-translocation bit it relies on is documented only in
Homebrew’s code, and DTS says the attribute’s format is not API.

**Destination:** `/Applications` when the user can write it, which admin-group members
can (measured), otherwise `~/Applications`, created if missing; never `sudo`. Before
installing, list every registered copy of the bundle id and refuse to add a second copy
in another Applications folder; report copies elsewhere (build folders) without touching
them.

**Replace:** stage the complete copy, verify it, rename the old copy aside, rename the
new one into place, then delete the old one; on `EPERM`, leave the old copy untouched
and name the App Management setting.
Register the new copy with `LSRegisterURL` so a LaunchServices lookup finds it before
first launch (whether this is needed is untested).

**Ownership:** a receipt outside the bundle (its path, version, digest, Team ID, and the
`metab` version that installed it) marks a copy `metab` owns.
A copy with a Caskroom link belongs to Homebrew, so `metab` defers to
`brew upgrade --cask`. Once Sparkle ships, the app updates itself, `metab` only
installs, and the cask declares `auto_updates true`. Uninstall moves the bundle to the
Trash and deletes the receipt; app data stays unless the user asks, as the cask’s `zap`
does.

**Choosing a version:** the newest `macos-v*` release whose host-protocol version this
`metab` accepts, read from a small manifest asset beside the ZIP. Releases are drafted
with `--latest=false`, so the “latest release” endpoint cannot select them.

## Recommendations

1. **Adopt design (a) as the CLI’s path to the app,** with modes to install, report
   status, and uninstall (names open).
   Modes are flags today (`--doctor`, `--plugins`), and a bare `metab app` would collide
   with `metab TARGET` for a folder named `app`. Opening stays the 2026-11-10 brief’s
   `--present`.
2. **Make the uvx path honest.** Under `uvx`, the install mode installs the app, then
   says the app needs a persistent CLI and prints
   `uv tool install metabrowser==<this version>`. The app’s “no runtime” screen keeps
   showing the same command.
3. **Publish the stapled ZIP and a manifest with every app release,** beside the DMG and
   its checksum. Turn on GitHub’s immutable releases for `macos-v*` tags, so published
   assets cannot be replaced (generally available since
   [2025-10-28](https://github.blog/changelog/2025-10-28-immutable-releases-are-now-generally-available/)).
   That setting is the owner’s call.
4. **Keep one owner per copy:** Homebrew for a cask install, `metab` for its own
   install, then Sparkle for both; fold `auto_updates true` into the update bead
   (`mb-fl72`).
5. **Do not pursue (b) or (c).** Revisit (b) only if PyPI becomes the only channel users
   can reach, and then carry a ZIP inside the wheel, which is (a) through PyPI.
6. **Make (a) and (d) write the same state,** so status, the app’s settings page, and
   `--doctor` report one install whichever direction it came from.
7. **Supply chain:** the app is first-party (a release of this repository), so the
   14-day cool-off does not apply, but the identity checks above run on every install
   and are not optional.

### CLI Parity

| New surface | `metab` equivalent | Evidence |
| --- | --- | --- |
| The installed copies, their versions, owners, and protocol compatibility (persisted state) | a status mode with `--json`, sharing a model with `--doctor --json` | a golden against fixture bundles and receipts, with the LaunchServices lookup and signature checks injected, so it runs on Linux CI |
| The install plan (release, URL, digest, destination, refusals) | the install mode with `--dry-run` | goldens for each refusal: dev variant, wrong Team ID, a second copy, a cask-owned copy, an unwritable destination |
| Uninstall | the uninstall mode | a golden on fixture bundles |
| Gatekeeper’s response, LaunchServices registration, app bundle protection, privacy prompts | shell- and platform-only exemptions, each named | a QA playbook run on clean accounts |

No route is added: installing an app is not something a running server should do, so
this is the case where a CLI mode beats a route.

### Gates Before Shipping the Install Mode

- A Developer ID–signed, notarized release exists (`mb-e9fm`).
- On clean macOS 15 and 26 accounts, one admin and one standard:
  - the install lands in `/Applications` and `~/Applications` respectively;
  - first launch shows no translocation and no approval prompt;
  - privacy prompts name the app;
  - the copy appears in Spotlight and the Apps view.
- Replacing a copy that has been launched, from Terminal without App Management, either
  succeeds or fails before touching the old copy.

### Falsifiable Claims

1. Once `metab` is running, installing the current 0.9 MB app takes under 5 s on a
   broadband link, with the signature and notarization checks under 2 s together.
2. The installed copy carries no `com.apple.quarantine`, is not translocated, and passes
   `spctl --assess` and `syspolicy_check distribution`.
3. A `metab` upgrade of a `metab`-owned copy between two Developer ID builds keeps its
   privacy grants, its Dock pin, and its defaults.
4. No `metab` install ever leaves a partial bundle in an Applications folder, including
   after `EPERM` or an interrupted download.
5. After `uv tool install metabrowser`, the app finds the CLI on first launch with no
   user action.

## Where This Breaks

- **Standard users:** `~/Applications` works, but its visibility in Spotlight and the
  Apps view is unverified on 15, 26, and 27.
- **Managed Macs:** MDM can restrict App Management or run endpoint security that kills
  unexpected code; a `.pkg` through Installer is the channel those fleets use.
- **No Gatekeeper prompt:** some users expect the “downloaded from the Internet” prompt
  as a safety signal, and a CLI install gives none.
- **Several copies with one bundle id:** LaunchServices already holds release-variant
  rehearsal builds on this Mac; which copy `open -b` launches among several is
  undocumented, so the release rehearsal could carry its own bundle id too.
- **A wheel-only world:** where GitHub is blocked but PyPI is not, (a) fails and (b)
  would work.

## Open Questions

- Does app bundle protection block renaming or deleting a whole launched bundle from
  Terminal, or only writes inside it?
  Does a process signed by the app’s own team count as same-team when Terminal is its
  responsible process?
- Do Spotlight and the macOS 26 Apps view list apps in `~/Applications`?
- Is `LSRegisterURL` needed for a LaunchServices lookup to find a freshly installed copy
  before it runs?
- How long does XProtect’s first-launch scan take for a copy that was never quarantined?
- Is `hdiutil` deprecated in macOS 27, as kitty’s installer says?
- Should the dev and release-rehearsal builds avoid LaunchServices registration, or get
  their own bundle ids, so a lookup by the release id finds only real installs?

## Next Steps

- [ ] Track design (a) as a bead under `mb-1apq`, with its parity rows and goldens.
- [ ] Add the stapled ZIP and a manifest to the release pipeline (`mb-nnhs`, `mb-e9fm`).
- [ ] Run the clean-account matrix above with the first Developer ID build.
- [ ] Add the bundle-id lookup to `metab`, shared with the front door (`mb-idri`).
- [ ] Fold `auto_updates true` and the one-owner rule into `mb-fl72`.

## Methodology

Three source-reading tracks ran in parallel on 2026-11-11, each limited to primary
sources: Python packaging tools and the uv and pipx trackers; apps, script installers,
and package managers; and Apple’s documentation, technotes, WWDC sessions, and DTS forum
posts, with Eclectic Light as secondary corroboration only.
Key claims from each track (Homebrew’s quarantine code, the uv, pipx, Homebrew, and Nix
issue states, Photini’s and menuinst’s install paths, Sparkle’s translocation and
write-access checks, WWDC22’s app management rules, Apple’s translocation text, and
DTS’s replacement advice) were re-read at their sources.
The local probes ran on one Mac, read-only outside a scratch directory.

**Not tested:** a Developer ID or notarized build of this app (none exists yet); a Mac
without developer tools; a standard (non-admin) account; macOS 15 or 27; Spotlight
indexing; any write to an Applications folder or the LaunchServices database.

## References

- Earlier briefs and plan:
  [Native macOS App for Metabrowser](research-2026-11-08-macos-app-packaging.md),
  [Server Topology, Lifecycle, and Agent Handoff](research-2026-11-10-native-app-server-topology.md),
  [Plan for the Native macOS App](../specs/active/plan-2026-11-10-native-macos-app.md)
- Repository: [Views, Models, and Routes](../architecture/arch-views-models-routes.md),
  [supply-chain policy](../../../SUPPLY-CHAIN-SECURITY.md), `apps/macos/README.md` and
  `apps/macos/packaging/metabrowser-app.rb.template` on the spike branch
- uv and pipx: [uv#13729](https://github.com/astral-sh/uv/issues/13729),
  [uv#12750](https://github.com/astral-sh/uv/issues/12750),
  [uv tools](https://github.com/astral-sh/uv/blob/0.13.7/docs/concepts/tools.md),
  [pipx#717](https://github.com/pypa/pipx/issues/717),
  [pipx scope](https://github.com/pypa/pipx/blob/1.18.16/docs/explanation/scope.rst),
  [wheel format](https://packaging.python.org/en/latest/specifications/binary-distribution-format/),
  [PEP 778](https://peps.python.org/pep-0778/)
- Python prior art: [menuinst](https://github.com/conda/menuinst),
  [pixi global manifest](https://github.com/prefix-dev/pixi/blob/v0.84.2/docs/global_tools/manifest.md),
  [Photini](https://github.com/jim-easterbrook/Photini),
  [pyshortcuts](https://github.com/newville/pyshortcuts),
  [desktop-app](https://github.com/chrisjbillington/desktop-app),
  [Briefcase](https://github.com/beeware/briefcase),
  [py2app](https://github.com/ronaldoussoren/py2app),
  [PyInstaller](https://github.com/pyinstaller/pyinstaller),
  [PyApp](https://github.com/ofek/pyapp)
- Apps and installers:
  [kitty installer](https://github.com/kovidgoyal/kitty/blob/v0.50.0/docs/installer.sh),
  [Zed install.sh](https://github.com/zed-industries/zed/blob/v1.27.0/script/install.sh),
  [VS Code shell command](https://github.com/microsoft/vscode/blob/1.146.0/src/vs/platform/native/electron-main/nativeHostMainService.ts#L551-L640),
  [Ollama](https://github.com/ollama/ollama/blob/v0.40.16/app/cmd/app/app_darwin.m),
  [LM Studio lms](https://github.com/lmstudio-ai/lms),
  [JupyterLab Desktop](https://github.com/jupyterlab/jupyterlab-desktop),
  [Claude Code deep links](https://code.claude.com/docs/en/deep-links),
  [LetsMove](https://github.com/potionfactory/LetsMove)
- Package managers: [Cask Cookbook](https://docs.brew.sh/Cask-Cookbook),
  [Homebrew quarantine](https://github.com/Homebrew/brew/blob/7.0.13/Library/Homebrew/cask/quarantine.rb),
  [brew#1808](https://github.com/Homebrew/brew/pull/1808),
  [nix-darwin#1396](https://github.com/nix-darwin/nix-darwin/pull/1396),
  [home-manager#8031](https://github.com/nix-community/home-manager/pull/8031),
  [mac-app-util](https://github.com/hraban/mac-app-util)
- Updates and integrity:
  [Sparkle installer launcher](https://github.com/sparkle-project/Sparkle/blob/2.10.1/InstallerLauncher/SUInstallerLauncher.m#L339-L393),
  [GitHub immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases),
  [verifying a release](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/verifying-the-integrity-of-a-release),
  [PyPI storage limits](https://docs.pypi.org/project-management/storage-limits/)
- Apple:
  [Packaging Mac software for distribution](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution),
  [Updating Mac Software](https://developer.apple.com/documentation/security/updating-mac-software),
  [WWDC22 10096](https://developer.apple.com/videos/play/wwdc2022/10096/),
  [TN3127](https://developer.apple.com/documentation/technotes/tn3127-inside-code-signing-requirements),
  [NSUpdateSecurityPolicy](https://developer.apple.com/documentation/bundleresources/information-property-list/nsupdatesecuritypolicy),
  [LSFileQuarantineEnabled](https://developer.apple.com/documentation/bundleresources/information-property-list/lsfilequarantineenabled),
  [Gatekeeper and runtime protection](https://support.apple.com/guide/security/gatekeeper-and-runtime-protection-sec5599b66df/web);
  DTS threads [706442](https://developer.apple.com/forums/thread/706442),
  [740680](https://developer.apple.com/forums/thread/740680),
  [732370](https://developer.apple.com/forums/thread/732370),
  [724969](https://developer.apple.com/forums/thread/724969),
  [678816](https://developer.apple.com/forums/thread/678816),
  [761436](https://developer.apple.com/forums/thread/761436),
  [779326](https://developer.apple.com/forums/thread/779326),
  [130560](https://developer.apple.com/forums/thread/130560)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
