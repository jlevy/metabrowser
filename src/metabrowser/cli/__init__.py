"""metabrowser CLI — single entry point for the `metabrowser` script.

The top-level `metabrowser` script dispatches to subcommands:

* `metabrowser serve ROOT` — launch the local web UI.
* `metabrowser plugins list` — list every discovered plugin.
* `metabrowser plugins show <name>` — full manifest for one plugin.
* `metabrowser plugins doctor` — sanity-check every discovered plugin.
* `metabrowser remote <host> --path <remote-root>` — SSH-tunnel into a remote
  `metabrowser serve`.

The legacy bare path form `metabrowser ./runs` still works via the top-level
``serve`` subcommand alias when no subcommand is given. The root path is required.
"""
