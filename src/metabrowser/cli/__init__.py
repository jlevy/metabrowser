"""Metabrowser command-line interface for the canonical `metab` script.

The top-level `metab` script dispatches to subcommands:

* `metab serve ROOT` — launch the local web UI.
* `metab plugins list` — list every discovered plugin.
* `metab plugins show <name>` — full manifest for one plugin.
* `metab plugins doctor` — sanity-check every discovered plugin.
* `metab remote <host> --path <remote-root>` — SSH-tunnel into a remote
  `metab serve`.

The `metabrowser` compatibility alias and the bare path form `metab ./runs` use the same
top-level callback. The root path is required.
"""
