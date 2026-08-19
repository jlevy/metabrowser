"""Read-only git access for the Git graph panel.

Core already depends on git for gitignore semantics and repository-root
discovery (see :mod:`metabrowser.ignore_filter` and
:func:`metabrowser.tree.build_gitignore_check`); this package extends that
dependency to reading history.

Layering, outermost first:

* :mod:`metabrowser.git.routes` — the ``/api/git/`` route table.
* :mod:`metabrowser.git.log` / :mod:`metabrowser.git.detail` — argument
  vectors and parsers for the two queries the panel needs.
* :mod:`metabrowser.git.repo` — repository identity, TTL-cached.
* :mod:`metabrowser.git.process` — the only place that spawns ``git``.
* :mod:`metabrowser.git.wire` — the JSON shapes all of the above emit.

Everything here is read-only. Nothing in this package stages, commits,
checks out, fetches, or otherwise mutates a repository.
"""

from __future__ import annotations
