# Changelog

All notable changes to Metabrowser are documented here.

## Unreleased

Flat single-command CLI:

- Serving is the default operation: `metab .` serves the current directory the way
  `open .` opens a folder on macOS. The `serve`, `walk`, `plugins`, and `remote`
  subcommands are removed and replaced by mode flags on one command: `--walk`,
  `--remote HOST`, `--plugins`, `--plugin NAME`, and `--doctor`.
- Exactly one mode applies per invocation.
  Options explicitly passed outside their mode are rejected as usage errors, and
  `--help` groups options by mode.
- Breaking change with no compatibility aliases: scripts that invoked a subcommand
  spelling must drop `serve` or switch to the matching mode flag.
  `metab --remote` starts the remote side with the flat syntax, so both hosts need a
  Metabrowser at or above this version.
- Golden console-output tests now pin the CLI surface (help, every mode, and the
  usage-error matrix) under `tests/golden/`.

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
