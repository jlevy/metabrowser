# Changelog

All notable changes to Metabrowser are documented here.

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
- MIT licensing, PyPI packaging, locked uv environments, and isolated wheel checks.
- Review hardening for bounded compressed reads, safe rendered labels, byte-accurate
  event streaming, renderer disposal, explicitly repository-configured development
  commands, and release builds without mutable dependency caches.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
