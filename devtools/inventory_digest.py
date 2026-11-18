"""Check that inventory providers give one corpus the same answers, before timing them.

A timing comparison between two providers is evidence only when both answered the same
questions with the same answers: a provider that indexed less, or classified
differently, is faster at something else. So a provider comparison starts here. For
each provider this runs the routes in `ROUTES`, the data routes whose answers come from
the inventory, through the in-process `--api` transport (`metabrowser.cli.asgi_client`)
in a fresh process with `METABROWSER_INVENTORY_PROVIDER` naming that provider, and
digests each normalized answer. Two providers pass when every digest matches; one
mismatch stops the comparison, and the route it names is where to look.

What is left out of a digest is what names the provider rather than the files: the
fields in `PROVIDER_FIELDS`, each with its reason. Anything else that differs is a
finding, timestamps included, because both providers stat the same files.

Usage::

    uv --config-file uv.toml run --frozen python -m devtools.inventory_digest \\
        .bench/corpus-100000 --provider python --provider other --json digest.json

Exit status 0 when every provider gave every route the same answer, 1 when any differs.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parent.parent

# The inventory-backed answers a browser builds a folder view from: root tallies, rows to
# a depth the tree shows, a grouped tree, the Overview rollup, Recent, the Quick File
# catalog, and the index metadata. Age groups are left out on purpose: their bands cut
# at the request's clock, which moves between one provider's process and the next.
ROUTES: tuple[str, ...] = (
    "/api/tree?depth=0",
    "/api/tree?depth=3",
    "/api/tree?depth=3&group_by=type",
    "/api/rollup?path=&depth=3",
    "/api/recent?window=all",
    "/api/catalog",
    "/api/index/meta",
)
# Top-level fields, by route path, that identify the provider rather than describe the
# files: its name, its watcher's selection on this host, and the catalog's revision,
# which counts the provider's own mutations.
PROVIDER_FIELDS: dict[str, frozenset[str]] = {
    "/api/catalog": frozenset({"revision"}),
    "/api/index/meta": frozenset({"provider", "watch_mode", "watch_state", "watch_reason"}),
}
# Long enough for the largest corpus a comparison runs on to finish its scan.
INDEX_TIMEOUT_S = 1_800.0


def canonical_digest(route: str, payload: object) -> dict[str, Any]:
    """The digest of *payload* without the fields that name its provider."""

    if isinstance(payload, dict):
        dropped = PROVIDER_FIELDS.get(urlsplit(route).path, frozenset())
        payload = {
            key: value
            for key, value in cast("dict[str, object]", payload).items()
            if key not in dropped
        }
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    data = text.encode("utf-8")
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


async def digest_routes(
    root: Path,
    routes: tuple[str, ...],
    *,
    provider: str,
    index_timeout_s: float = INDEX_TIMEOUT_S,
) -> dict[str, Any]:
    """Digest *routes* as the provider this process selects answers them for *root*."""

    from metabrowser import server
    from metabrowser.cli.asgi_client import InProcessClient, wait_for_index
    from metabrowser.normalize import NormalizeContext, normalize_payload

    server._set_root_dir(root)  # pyright: ignore[reportPrivateUsage]
    context = NormalizeContext(root=root)
    digests: dict[str, Any] = {}
    async with InProcessClient(cast(Any, server.app), label="inventory digest") as client:
        waited = await wait_for_index(client, timeout_s=index_timeout_s)
        if not waited.completed:
            raise SystemExit(f"{provider}: the index did not finish: {waited.detail}")
        meta: Any = (await client.get("/api/index/meta")).json()
        served = cast("dict[str, Any]", meta).get("provider") if isinstance(meta, dict) else None
        if served != provider:
            raise SystemExit(f"requested provider {provider!r}, but {served!r} served")
        for route in routes:
            response = await client.get(route)
            if response.incomplete or response.status_code != 200:
                raise SystemExit(f"{provider}: {route} answered HTTP {response.status_code}")
            digests[route] = canonical_digest(route, normalize_payload(response.json(), context))
    return {"provider": provider, "routes": digests}


def digest_in_fresh_process(
    root: Path, provider: str, routes: tuple[str, ...], index_timeout_s: float
) -> dict[str, Any]:
    """Run :func:`digest_routes` for *provider* in its own interpreter and read it back."""

    environment = os.environ.copy()
    environment["METABROWSER_INVENTORY_PROVIDER"] = provider
    command = [
        sys.executable,
        "-m",
        "devtools.inventory_digest",
        str(root),
        "--one",
        provider,
        "--index-timeout",
        str(index_timeout_s),
        *(argument for route in routes for argument in ("--route", route)),
    ]
    completed = subprocess.run(
        command, capture_output=True, text=True, check=False, cwd=REPO, env=environment
    )
    if completed.returncode != 0:
        raise SystemExit(f"{provider}: digest failed:\n{completed.stderr[-2000:]}")
    loaded: Any = json.loads(completed.stdout.strip().splitlines()[-1])
    return cast("dict[str, Any]", loaded)


def mismatched_routes(results: list[dict[str, Any]]) -> list[str]:
    """Routes whose digest is not the same for every provider in *results*."""

    if not results:
        return []
    routes = cast("dict[str, Any]", results[0]["routes"])
    return [
        route
        for route in routes
        if len({cast("dict[str, Any]", result["routes"])[route]["sha256"] for result in results})
        != 1
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("root", type=Path, help="the corpus to digest")
    parser.add_argument(
        "--provider",
        action="append",
        default=[],
        help="a provider to digest; repeat to compare several (default: python)",
    )
    parser.add_argument(
        "--route", action="append", default=[], help="a route to digest instead of ROUTES"
    )
    parser.add_argument("--index-timeout", type=float, default=INDEX_TIMEOUT_S)
    parser.add_argument("--json", type=Path, help="also write the digests here")
    parser.add_argument("--one", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = cast("Path", args.root).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"{root} is not a directory")
    routes = tuple(cast("list[str]", args.route)) or ROUTES
    timeout = cast("float", args.index_timeout)
    one = cast("str | None", args.one)
    if one is not None:
        result = asyncio.run(digest_routes(root, routes, provider=one, index_timeout_s=timeout))
        print(json.dumps(result))
        return 0

    from metabrowser.inventory_engine.factory import resolve_inventory_provider

    providers = [
        resolve_inventory_provider(name).value for name in cast("list[str]", args.provider)
    ] or ["python"]
    results = [digest_in_fresh_process(root, name, routes, timeout) for name in providers]
    mismatched = mismatched_routes(results)
    report = {"root": str(root), "results": results, "mismatched_routes": mismatched}
    output = cast("Path | None", args.json)
    if output is not None:
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for route in routes:
        digests = "  ".join(
            f"{result['provider']}={cast('dict[str, Any]', result['routes'])[route]['sha256'][:12]}"
            for result in results
        )
        print(f"{'DIFFERS' if route in mismatched else 'same   '}  {route}  {digests}")
    return 1 if mismatched else 0


if __name__ == "__main__":
    sys.exit(main())
