"""Exercise a folder collection through the same routes as other table sources."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest
from softschema import collection
from starlette.applications import Starlette
from starlette.testclient import TestClient

from metabrowser import server
from metabrowser.builtin_plugins.softschema import indexer
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


def test_collection_reports_discovery_before_the_index_is_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server._set_root_dir(tmp_path)
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    _schema(contracts, "Person", {"name": {"type": "string"}})
    _record(tmp_path, "people", "Person", "ada", {"name": "Ada Lovelace"})
    reached_record = threading.Event()
    resume = threading.Event()
    scan_collection = collection.scan_collection

    def isolated_database(_index: indexer.CollectionIndex) -> Path:
        return tmp_path / ".snapshot.sqlite"

    monkeypatch.setattr(indexer.CollectionIndex, "_database", isolated_database)

    def paused_scan(root: Path, **kwargs: Any) -> collection.CollectionScan:
        ignore = kwargs.pop("ignore")

        def pause_after_record(path: str, is_directory: bool) -> bool:
            skipped = ignore(path, is_directory)
            if path == "people/ada.json":
                reached_record.set()
                assert resume.wait(10), "test did not release the scanner"
            return skipped

        return scan_collection(root, ignore=pause_after_record, **kwargs)

    monkeypatch.setattr(collection, "scan_collection", paused_scan)
    plugins = [p for p in server._LOADED_PLUGINS if p.name == "softschema"]
    route = "/api/plugin/softschema/collection"
    with TestClient(Starlette(routes=build_plugin_routes(plugins))) as client:
        try:
            started = client.get(route, params={"path": "people"})
            assert started.json()["state"] == "indexing"
            assert reached_record.wait(10), "scanner did not reach the record"
            progress = client.get(route, params={"path": "people"}).json()
            assert progress["state"] == "indexing"
            assert progress["paths_checked"] > 0
            assert progress["tables"] == []
        finally:
            resume.set()
        ready = client.get(route, params={"path": "people", "wait": "1"}).json()
        assert ready["state"] == "ready"
        assert ready["paths_checked"] >= progress["paths_checked"]
        assert ready["tables"][0]["count"] == 1


def test_folder_tables_link_across_scopes_and_keep_current_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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

        monkeypatch.setattr(indexer, "_REFRESH_SECONDS", 0)
        unchanged = client.get(
            "/api/plugin/softschema/collection", params={"path": "people", "wait": "1"}
        ).json()
        assert unchanged["generation"] == overview.json()["generation"]

        _record(tmp_path, "people", "Person", "ada", {"name": "Ada Byron"})
        refresh = client.get(
            "/api/plugin/softschema/collection", params={"path": "people", "wait": "1"}
        ).json()
        assert refresh["generation"] != unchanged["generation"]
        updated = client.get("/api/plugin/table/record", params={**person, "key": ada["key"]})
        assert updated.json()["label"] == "Ada Byron"


@pytest.mark.parametrize("bound", [True, False])
def test_table_fields_use_only_schemas_bound_to_its_records(tmp_path: Path, bound: bool) -> None:
    server._set_root_dir(tmp_path)
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    contract = "test.collection:Person/v1"
    definitions = {
        "00-unused": {
            "name": {"type": "integer", "title": "Unused name"},
            "ghost": {"type": "string"},
        },
        "Person": {"name": {"type": "string", "title": "Bound name"}},
        "Zebra": {"note": {"type": "string", "title": "Bound note"}},
    }
    for name, props in definitions.items():
        (contracts / f"{name}.schema.json").write_text(
            json.dumps(
                {
                    "type": "object",
                    "properties": {"id": {"type": "string"}, **props},
                    "x-softschema": {"contract": contract},
                }
            )
        )
    people = tmp_path / "people"
    people.mkdir()
    for name, values in [("Person", {"name": "Ada"}), ("Zebra", {"note": "Extra field"})]:
        pointer = name if bound else "missing"
        (people / f"{name}.json").write_text(
            json.dumps(
                {
                    "softschema": {
                        "contract": contract,
                        "schema": f"../contracts/{pointer}.schema.json",
                        "envelope": "data",
                    },
                    "data": {"id": f"person:{name}", **values},
                }
            )
        )
    plugins = [p for p in server._LOADED_PLUGINS if p.name in ("table", "softschema")]
    with TestClient(Starlette(routes=build_plugin_routes(plugins))) as client:
        answer = client.get(
            "/api/plugin/table/schema",
            params={"path": "", "table": contract, "wait": "1"},
        )
        assert answer.status_code == 200, answer.text
        fields = {field["name"]: field for field in answer.json()["fields"]}
        assert "ghost" not in fields
        assert fields["name"]["type"] == "text"
        assert fields["name"]["title"] == ("Bound name" if bound else None)
        assert fields["note"]["title"] == ("Bound note" if bound else None)
