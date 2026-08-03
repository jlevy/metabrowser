# Changelog

All notable changes to Metabrowser are documented here.

## Unreleased

Agent Skill:

- The skill now prefers a locally installed `metab` and falls back to the pinned
  `uvx metabrowser@0.2.0` runner, instead of reaching for the runner first.
  The zero-install guarantee is unchanged; an agent that already has Metabrowser no
  longer pays a `uvx` resolve.
- The skill declares its `compatibility` requirement (a local `metab`, or uv with
  network access on first use).
- The installation guide documents a reproducible install form that pins both the
  installer version and the source tag, alongside the existing interactive shorthand.
- Tests assert the documented `metabrowser` pins agree across the skill, README, and
  installation guide, so pin drift fails on the pull request instead of at release.

## 0.2.0

Flat single-command CLI:

- Serving is now the default operation: `metab .` serves the current directory the way
  `open .` opens a folder on macOS. The `serve`, `walk`, `plugins`, and `remote`
  subcommands are removed and replaced by mode flags on one command: `--walk`,
  `--remote HOST`, `--plugins`, `--plugin NAME`, and `--doctor`.
- Exactly one mode applies per invocation.
  Options explicitly passed outside their mode are rejected as usage errors, and
  `--help` groups options by mode.
- This is a breaking change with no compatibility aliases: scripts that invoked a
  subcommand spelling must drop `serve` or switch to the matching mode flag.
  `metab --remote` starts the remote side with the flat syntax, so both hosts need
  Metabrowser 0.2.0 or newer.
- The Agent Skill, README, and installation guide pin `uvx metabrowser@0.2.0`, the first
  release with the flat CLI.

KPress embedding and visual consistency:

- KPress is upgraded to `0.3.0` and its declarative fragment architecture.
  Metabrowser owns one root theme attribute and one root type-size hook, fragments are
  theme-agnostic, the KPress asset manifest is authoritative, and host-side heading,
  bullet, theme-restamping, resolver-filtering, and numeric-table workarounds are
  removed.
- Embedded document prose is now 15px, down from 17px and one step above the 14px app
  body. KPress derives headings from that base, while proportional host tokens keep code
  and secondary text tied to it, so the document hierarchy stays stable when the browser
  root size changes.
- Embedded document navigation now matches KPress’s polished static-site treatment:
  compact hierarchy and active states in the narrow drawer, plus a borderless docked
  rail at the wide document breakpoint.
- Theme changes now keep embedded KPress content, full-file syntax highlighting, and
  plugin charts aligned with the Metabrowser chrome.
  The host owns the complete Highlight.js palette with WCAG AA contrast checks in both
  themes. Token-colored SDK and built-in canvas charts repaint when the resolved palette
  changes and release their theme subscriptions through the existing chart `destroy()`
  lifecycle.

Reliability and distribution:

- Pressing Ctrl-C twice now forces an immediate server exit without non-actionable
  Uvicorn cancellation tracebacks.
  Graceful shutdown keeps normal error reporting, and every exit path restores the
  process-global logger state for later in-process runs.
- Repository and package metadata now state AGPL-3.0-or-later explicitly, matching the
  license obligation that has always applied through the required KPress runtime.
  Vendored browser components remain under their own licenses in `NOTICE.md`, and built
  distributions verify the license expression and include both license files.
- The publish workflow refuses a release whose tag does not match the Agent Skill,
  README, and installation-guide version pins.
  After publishing, it smoke-tests the pinned Skill invocation with `--help` and
  `--doctor` directly from PyPI.

Contributor workflow:

- Golden console-output tests now pin the CLI surface (help, every mode, and the
  usage-error matrix) under `tests/golden/`, run with tryscript
  (github.com/jlevy/tryscript) via `make test` and regenerated with
  `make golden-update`.
- Repository automation is updated to tbd 0.4.2. Its exact fallback stays usable under
  the dependency cool-off policy, and release documentation incorporates the verified
  GitHub CLI workflow for proxied agent sessions.

## 0.1.1

Hardening, offline support, and UI refinement:

- Offline-first assets: every third-party browser library is vendored into the wheel
  from lockfile-verified npm packages with a hash manifest, license texts, and size
  caps. The served page references no external origins, so Metabrowser works without
  network access; unused elkjs was dropped.
- Host-header validation defends against DNS rebinding.
  Loopback names and a concrete `--host` value are permitted automatically; wildcard
  binds keep validation and use loopback for the printed URL and auto-open, and
  `METABROWSER_ALLOWED_HOSTS` extends the allowlist (see SECURITY.md).
- First-paint navigation expands folders within a visible-row budget instead of
  expanding every top-level folder; document and tab spacing tightened, prose sized
  relative to navigation, compact TOC rows, and Markdown tables right-align signed
  percentages and localized number formats.
- Server responsiveness: live-tail polling, watcher classification, active-file sweeps,
  and synchronous plugin data hooks no longer block the event loop, and the mtime cache
  no longer serializes reads behind slow filesystem stats.
- Browser resilience: superseded file loads abort, client caches are bounded, the
  inventory event stream reconnects with backoff after repeated failures, live tree
  updates handle filenames containing backslashes and quotes, and the SDK owns
  copy-button behavior end to end.
- Documentation: project design records reorganized under a dedicated records tree with
  maintained architecture documents and dated plans, plus a research brief on the
  planned diff viewer architecture.
- Licensing: Metabrowser is licensed under AGPL-3.0-or-later, aligned with its required
  KPress runtime. Vendored browser components remain under their own licenses listed in
  `NOTICE.md`.

## 0.1.0

Initial standalone release:

- Local file, log, Markdown, structured-data, image, and binary browsing.
- Primary `metab` command with a `metabrowser` compatibility alias.
- Concise zero-install and global-tool onboarding, plus a portable Agent Skill that
  delegates to the pinned `uvx metabrowser@0.1.0` runner.
- Trusted manifest-driven plugins with JavaScript views and Python data hooks.
- KPress-backed Markdown rendering through `kpress==0.2.2`.
- Gzip- and zlib-transparent previews, frontmatter classification, Markdown rendering,
  and KPress export with bounded input, output, and text windows.
- Background inventory indexing, live filesystem updates, and recent-file navigation.
- SSH and optional GCP remote tunnels.
- AGPL-3.0-or-later licensing, PyPI packaging, locked uv environments, and isolated
  wheel checks.
- Review hardening for bounded compressed reads, safe rendered labels, byte-accurate
  event streaming, renderer disposal, explicitly repository-configured development
  commands, and release builds without mutable dependency caches.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
