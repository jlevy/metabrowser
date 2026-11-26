"""Exercise a folder collection through the same routes as other table sources."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.plugin_loader.static_assets import build_plugin_routes


def _schema(root: Path, name: str, props: dict[str, Any]) -> None:
    marker = {"contract": f"test.collection:{name}/v1"}
    (root / f"{name}.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"id": {"type": "string"}, **props},
                "required": ["id", *props],
                "x-softschema": marker,
            }
        )
    )


def _record(root: Path, folder: str, name: str, key: str, values: dict[str, Any]) -> None:
    directory = root / folder
    directory.mkdir(exist_ok=True)
    (directory / f"{key}.json").write_text(
        json.dumps(
            {
                "softschema": {
                    "contract": f"test.collection:{name}/v1",
                    "schema": f"../contracts/{name}.schema.json",
                    "envelope": "data",
                    "status": "enforced",
                },
                "data": {"id": f"{name}:{key}", **values},
            }
        )
    )


def test_folder_tables_link_across_scopes_and_keep_current_generation(tmp_path: Path) -> None:
    server._set_root_dir(tmp_path)
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    _schema(contracts, "Person", {"name": {"type": "string"}})
    _schema(contracts, "Order", {"buyer": {"type": "string"}, "seller": {"type": "string"}})
    _record(tmp_path, "people", "Person", "ada", {"name": "Ada Lovelace"})
    _record(tmp_path, "people", "Person", "grace", {"name": "Grace Hopper"})
    _record(tmp_path, "orders", "Order", "one", {"buyer": "Person:ada", "seller": "Person:grace"})
    _record(tmp_path, "orders", "Order", "two", {"buyer": "Person:grace", "seller": "Person:ada"})

    plugins = [p for p in server._LOADED_PLUGINS if p.name in ("table", "softschema")]
    with TestClient(Starlette(routes=build_plugin_routes(plugins))) as client:
        overview = client.get(
            "/api/plugin/softschema/collection", params={"path": "people", "wait": "1"}
        )
        assert overview.status_code == 200, overview.json()
        assert overview.json()["root"] == ""
        assert overview.json()["state"] == "ready"
        assert overview.json()["tables"] == [
            {"count": 2, "id": "test.collection:Person/v1", "label": "Person/v1"}
        ]

        person = {"path": "people", "table": "test.collection:Person/v1"}
        rows = client.get("/api/plugin/table/rows", params=person).json()
        ada = rows["rows"][0]
        detail = client.get("/api/plugin/table/record", params={**person, "key": ada["key"]}).json()
        assert detail["label"] == "Ada Lovelace"
        assert detail["source_path"] == "people/ada.json"
        assert [(ref["fields"], ref["count"]) for ref in detail["referenced_by"]] == [
            (["buyer"], 1),
            (["seller"], 1),
        ]
        incoming = client.get(
            "/api/plugin/table/rows",
            params={
                "path": "",
                "table": "test.collection:Order/v1",
                "via": json.dumps([["seller"], ["id"]]),
                "ref": f"test.collection:Person/v1:{ada['key']}",
            },
        )
        assert incoming.status_code == 200, incoming.json()
        assert incoming.json()["count"] == 1
        assert incoming.json()["rows"][0]["cells"]["seller"]["ref"]["label"] == "Ada Lovelace"
        assert (
            incoming.json()["generation"] == detail["generation"] == overview.json()["generation"]
        )
