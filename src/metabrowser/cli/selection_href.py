"""The address a provider web URL's selection opens at, given its path in the tree.

Serving a URL computes it once the mirror has said where the URL's ref ends
(``cli/selection.py``, ``cli/git_pin_cli.py``); ``--present`` computes it without a
mirror (``cli/present.py``). It reads nothing, so ``--present`` imports it without the
acquisition and resolution modules the serving path loads.
"""

from __future__ import annotations

from metabrowser.cache.urls import RepositorySelection
from metabrowser.git.tree_source import GitPath
from metabrowser.view_routes import VIEW_ROUTE_PREFIX, format_commit_href, format_pull_href


def selection_view_href(
    selection: RepositorySelection,
    path: tuple[bytes, ...],
    *,
    commit: str | None = None,
    pull_file: str = "",
) -> str:
    """The address a served URL selection opens at, with *path* its path in the tree.

    A file or folder opens at its `/view/` address. A file keeps the URL's `plain=1`
    and line anchor, either of which opens the file's Source view in the browser, where
    the anchor highlights its lines. A pull request opens at its page, `/pull/<n>`, on
    the tab the URL names, as `/pull/<n>/files` does, and on the Changes tab at
    *pull_file*, the changed file its anchor names once the provider has resolved it
    (`/pull/<n>/files/<path>`); without one, at the tab. A commit opens at its page,
    `/commit/<id>`, given *commit*, the full ID the mirror resolved the URL's to, which is
    what the commit route needs; without it, at the tree.
    """

    if selection.kind == "pull_request" and selection.pull_request is not None:
        file = pull_file if selection.pull_tab == "files" else ""
        return format_pull_href(selection.pull_request, selection.pull_tab, file)
    if selection.kind == "commit" and commit is not None:
        return format_commit_href(commit)
    if selection.kind not in {"tree", "blob"} or not path:
        return VIEW_ROUTE_PREFIX
    href = VIEW_ROUTE_PREFIX + GitPath(path).to_wire()
    if selection.kind == "tree":
        href += "/"
    if selection.kind == "blob" and selection.plain:
        href += "?plain=1"
    if selection.kind == "blob" and selection.lines is not None:
        href += "#" + selection.lines.fragment()
    return href


__all__ = ["selection_view_href"]
