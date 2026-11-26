"""A stand-in for the ``metab ROOT`` that ``--present`` starts for a browser.

``cli/present.py`` ``serve_detached`` starts serve mode and reports it started once the
address its ``Serving <root> at <url>`` line names answers ``GET /api/identity`` for the
target. This one does the same in milliseconds and opens no browser. Run it as
``python tests/present_server_standin.py [--path P] -- ROOT``. It listens on a free
loopback port, prints the line with that port, and answers the route for ROOT as a
server of ROOT does (``root_identity.py``):

- a local folder, or a file's folder, by its absolute path, with the home folder as
  ``~``, and ``kind`` ``git`` for a folder that holds a ``.git`` entry, as a checkout is,
  and ``folder`` for any other;
- a GitHub URL by its repository without the scheme, then ``#<n>`` for a pull request
  and ``@main`` otherwise, and ``kind`` ``mirror``.

Every other request is a 404. ``SERVER_STAND_IN_TAKEN_URL`` makes it the server that
loses its port instead: it prints that address, which another server holds, waits a
moment as uvicorn's startup does, and exits 1 with the line uvicorn writes when the bind
fails.
"""

from __future__ import annotations

import http.server
import json
import os
import sys
import time
from pathlib import Path
from typing import ClassVar, override

# How long the server that loses its port takes to find out, as uvicorn runs the
# lifespan before it binds: long enough that `--present` would have reported the line.
TAKEN_EXIT_DELAY_S = 0.5


def identity(root: str) -> dict[str, str]:
    """What a server of *root* answers ``GET /api/identity`` with, as far as it is read."""

    if "://" in root or root.startswith("git@"):
        # `https://host/owner/repo[/pull/N…]` or `git@host:owner/repo.git`.
        host, _, rest = (
            root.split("://", 1)[-1].removeprefix("git@").replace(":", "/", 1).partition("/")
        )
        owner, repo, *more = rest.split("/")
        origin = f"{host}/{owner}/{repo.removesuffix('.git')}"
        pinned = f"#{more[1]}" if more[:1] == ["pull"] and len(more) > 1 else "@main"
        return {"kind": "mirror", "full_name": origin + pinned}
    folder = Path(root).resolve()
    if folder.is_file():
        folder = folder.parent
    home = Path.home().resolve()
    if folder == home:
        name = "~"
    elif folder.is_relative_to(home):
        name = f"~/{folder.relative_to(home)}"
    else:
        name = str(folder)
    return {"kind": "git" if (folder / ".git").exists() else "folder", "full_name": name}


class _Identity(http.server.BaseHTTPRequestHandler):
    answer: ClassVar[bytes] = b""

    def do_GET(self) -> None:
        if self.path != "/api/identity":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(self.answer)))
        self.end_headers()
        self.wfile.write(self.answer)

    @override
    def log_message(self, format: str, *args: object) -> None:
        del format, args


def main(arguments: list[str]) -> int:
    root = arguments[-1]
    taken = os.environ.get("SERVER_STAND_IN_TAKEN_URL", "")
    if taken:
        print(f"Serving {root} at {taken}", flush=True)
        time.sleep(TAKEN_EXIT_DELAY_S)
        print(
            "ERROR:    [Errno 48] error while attempting to bind on address: "
            "address already in use",
            file=sys.stderr,
            flush=True,
        )
        return 1
    _Identity.answer = json.dumps(identity(root)).encode()
    with http.server.HTTPServer(("127.0.0.1", 0), _Identity) as server:
        port = server.server_address[1]
        print(f"Serving {root} at http://127.0.0.1:{port}/view/", flush=True)
        server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
