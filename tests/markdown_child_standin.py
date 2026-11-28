"""A stand-in for the Markdown child that speaks its frames and does what the text says.

``diff/markdown_projection_worker.py`` runs the real child, which imports KPress and
renders; this one answers in milliseconds, so a test of the worker's queue, deadline,
cancellation, and recovery runs in about a second and without KPress. Run it as
``python tests/markdown_child_standin.py``. It says it is ready, then answers each
request by the first line of the render's text:

- ``sleep <seconds>``: wait, then answer as ``echo`` does;
- ``exit``: exit without answering;
- ``crash``: write a line to standard error, then exit without answering;
- ``error``: KPress's render error, ``{"error": "render", ...}``;
- ``invalid``: KPress's invalid request;
- ``garbage``: a frame that is not JSON;
- ``shapeless``: a render with no ``inert`` flag;
- ``pid``: a render whose HTML is this process's ID;
- anything else (``echo``): a render whose HTML is the text, inert for a document,
  with the front matter and its error as the frame carried them.

A projection is answered ``ready`` with no blocks. ``--slow-start <seconds>`` waits
before the ready frame.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
from typing import Any


def _write(sink: Any, payload: object) -> None:
    data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    sink.write(len(data).to_bytes(4, "big") + data)
    sink.flush()


def _render(request: dict[str, Any]) -> object:
    text = base64.b64decode(request["source"]).decode()
    command, _, rest = text.partition("\n")[0].partition(" ")
    if command == "sleep":
        time.sleep(float(rest))
    if command == "memory":
        os._exit(int(sys.argv[sys.argv.index("--rss-exit") + 1]))
    if command == "exit":
        os._exit(3)
    if command == "crash":
        sys.stderr.write("stand-in crashed\n")
        sys.stderr.flush()
        os._exit(3)
    if command == "error":
        return {"error": "render", "message": "boom"}
    if command == "invalid":
        return {"error": "invalid", "message": "no such profile"}
    if command == "garbage":
        return b"not json"
    html = str(os.getpid()) if command == "pid" else f"<p>{text}</p>"
    if command == "shapeless" or request.get("link_base") is not None:
        return {"rendered": {"html": html}}
    return {
        "rendered": {
            "html": html,
            "inert": True,
            "frontmatter": request["frontmatter"],
            "frontmatter_error": request["frontmatter_error"],
        }
    }


def main() -> None:
    if "--slow-start" in sys.argv:
        time.sleep(float(sys.argv[sys.argv.index("--slow-start") + 1]))
    source, sink = sys.stdin.buffer, sys.stdout.buffer
    _write(sink, {"ready": True})
    while len(header := source.read(4)) == 4:
        request = json.loads(source.read(int.from_bytes(header, "big")))
        if request.get("op") != "render" and "--rss-exit" in sys.argv:
            os._exit(int(sys.argv[sys.argv.index("--rss-exit") + 1]))
        if request.get("op") == "render":
            _write(sink, _render(request))
        else:
            _write(
                sink,
                {
                    "projection": {
                        "version": 1,
                        "status": "ready",
                        "blocks": [],
                        "source_only": False,
                    },
                    "references": [],
                },
            )


if __name__ == "__main__":
    main()
