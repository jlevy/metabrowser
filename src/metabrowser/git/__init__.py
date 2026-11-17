"""Read-only Git access: history, commit detail, and pinned-revision trees.

Layering, outermost first:

* :mod:`metabrowser.git.routes` — the ``/api/git/`` route table.
* :mod:`metabrowser.git.content_routes` — the content routes on a pinned revision.
* :mod:`metabrowser.git.history` — bounded, replayable history sessions.
* :mod:`metabrowser.git.log` / :mod:`metabrowser.git.detail` — argument
  vectors and parsers for refs, log records, and one commit.
* :mod:`metabrowser.git.repo` — repository identity, TTL-cached.
* :mod:`metabrowser.git.ref_state` / :mod:`metabrowser.git.route_memo` — the
  refs' state, and answers kept under it.
* :mod:`metabrowser.git.tree_source` — ``GitPath`` and batch blob reads.
* :mod:`metabrowser.git.process` — where every ``git`` process starts.
* :mod:`metabrowser.git.wire` — the JSON shapes the routes emit.

Nothing here stages, commits, or checks out. The readers and routes never
fetch; :mod:`metabrowser.git.process` also runs the fetches that
:mod:`metabrowser.cache` asks for, under its acquisition policy.
``docs/project/architecture/arch-git.md`` describes the package.
"""

from __future__ import annotations
