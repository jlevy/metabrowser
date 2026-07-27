"""Metabrowser command-line interface for the canonical `metab` script.

`metab` is one flat command whose default operation is serving:

* `metab ROOT`: launch the local web UI.
* `metab ROOT --walk`: inventory walk with no server.
* `metab --remote <host> --path <remote-root>`: SSH-tunnel into a remote
  `metab` server.
* `metab --plugins`: list every discovered plugin.
* `metab --plugin <name>`: full manifest for one plugin.
* `metab --doctor`: sanity-check every discovered plugin.

The `metabrowser` compatibility alias uses the same entry point.
See `metabrowser.cli.main` for mode resolution and option applicability.
"""
