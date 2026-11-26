"""The stand-in plugin's data hooks: the ones the spike's host calls, and the probes' own."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from typing import Any, Protocol

import metabrowser
from metabrowser import ArtifactPath, detect_adapter, extract_agent_charts_cached, resolve_path


class Request(Protocol):
    @property
    def query_params(self) -> Mapping[str, str]: ...


class Bytes:
    """A response by its ``status_code``, ``body``, and ``raw_headers``, without Starlette."""

    def __init__(self, body: bytes) -> None:
        self.status_code = 200
        self.body = body
        self.raw_headers = [(b"content-type", b"application/octet-stream")]


def info(request: Request) -> dict[str, Any]:
    return {
        "routes": ["info", "viz-model", "charts"],
        "runtime_version": getattr(metabrowser, "__version__", None),
    }


def viz_model(request: Request) -> dict[str, Any]:
    spec = resolve_path(request.query_params["process"])
    if spec is None:
        return {"error": "not found"}
    text = spec.read_text()
    return {"nodes": [{"index": index, "text": text} for index in range(2000)]}


def charts(request: Request) -> dict[str, Any]:
    target = resolve_path(request.query_params["path"])
    if target is None:
        return {"error": "not found"}
    with ArtifactPath(target).open_text() as handle:
        lines = [line for _, line in zip(range(20), handle, strict=False)]
    adapter = detect_adapter(lines)
    if adapter == "pool":
        return {"charts": [], "summary": {"adapter": adapter}}
    payload = extract_agent_charts_cached(target)
    return {"charts": (payload or {}).get("charts"), "summary": None, "adapter": adapter}


def blob(request: Request) -> Bytes:
    return Bytes(b"x" * int(request.query_params["n"]))


async def blocking_async(request: Request) -> dict[str, Any]:
    """An ``async def`` hook that blocks, so it holds the worker's event loop."""
    time.sleep(float(request.query_params.get("seconds", "30")))  # noqa: ASYNC251
    return {"slept": True}


def slow_sync(request: Request) -> dict[str, Any]:
    time.sleep(float(request.query_params.get("seconds", "5")))
    return {"slept": True}


def spawn_child(request: Request) -> dict[str, Any]:
    """A long-lived subprocess, as a hook that shells out to a tool would leave behind."""
    child = subprocess.Popen(["/bin/sleep", request.query_params.get("seconds", "300")])
    return {"child_pid": child.pid}


def fork_writes_protocol(request: Request) -> dict[str, Any]:
    """A forked child inherits the protocol descriptors, which an exec'd one does not."""
    pid = os.fork()
    if pid == 0:
        try:
            os.write(int(sys.argv[3]), b"garbage from a forked child\n")
            code = 0
        except OSError:
            code = 7
        os._exit(code)
    _, status = os.waitpid(pid, 0)
    return {"child_exit": os.waitstatus_to_exitcode(status)}


def _attempt(action: Callable[[], object]) -> str:
    try:
        action()
    except PermissionError:
        return "denied"
    except OSError as exc:
        return f"failed: {type(exc).__name__}"
    return "allowed"


def _write(path: str) -> None:
    with open(path, "w") as handle:
        handle.write("x")
    os.remove(path)


def _connect(port: str) -> None:
    with socket.create_connection(("127.0.0.1", int(port)), timeout=2):
        pass


def reach(request: Request) -> dict[str, str]:
    """What this worker's authority lets a hook do, by what happened and never by a path."""
    query = request.query_params
    return {
        "read the served root": _attempt(lambda: os.listdir(str(resolve_path("")))),
        "read a file outside its grants": _attempt(lambda: open(query["outside"]).read()),
        "write beside that file": _attempt(lambda: _write(query["outside"] + ".probe")),
        "write in its scratch folder": _attempt(lambda: _write(query["scratch"] + "/probe")),
        "connect over TCP": _attempt(lambda: _connect(query["port"])),
        "start a system tool": _attempt(lambda: subprocess.run(["true"], check=True)),
    }


def native_sleep(request: Request) -> dict[str, Any]:
    """A synchronous hook inside native code that keeps the interpreter lock, so no other
    Python thread in the worker runs until it returns."""
    import ctypes

    ctypes.PyDLL(None).sleep(int(request.query_params.get("seconds", "5")))
    return {"slept": True}
