"""Project one immutable SoftSchema snapshot onto the shared table protocol."""

from __future__ import annotations

import hashlib
import json
import threading
from array import array
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from dataclasses import field as dc_field
from typing import TYPE_CHECKING, Any, cast

from metabrowser.builtin_plugins.table import memory
from metabrowser.plugin_api import (
    TABLE_CARD_MAX_FIELDS,
    TABLE_CELL_PREVIEW_CHARS,
    TABLE_RECORD_VALUE_BYTES,
    BackrefCount,
    Budget,
    Cell,
    FieldRef,
    FieldType,
    FolderTableHandle,
    RecordNotFoundError,
    SourceUnreadableError,
    TableCard,
    TableField,
    TableInfo,
    TableNotFoundError,
    TablePage,
    TableQuery,
    TableRecord,
    TableSchema,
    coerce_filter_value,
    integer_cell,
    parse_position_key,
    real_cell,
    stored_cell,
    text_cell,
)

from .indexer import INDEX_WAIT_SECONDS, index_for
from .offer import collection_root

if TYPE_CHECKING:
    from softschema.collection import CollectionRecord, CollectionScan
    from softschema.schema_view import FieldInfo

_PROBLEMS = "$problems"
_FIELD_TYPES: Mapping[str, FieldType] = {
    "string": "text",
    "integer": "integer",
    "number": "real",
    "boolean": "boolean",
    "object": "json",
    "array": "json",
}
_PAGE_COLUMNS = 12


def _key(path: str) -> str:
    return "r." + hashlib.sha256(path.encode("utf-8")).hexdigest()


def _type(value: object) -> FieldType:
    if isinstance(value, str):
        return "text"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "real"
    return "json"


def _sort(value: object) -> memory.SortKey:
    if value is None:
        return memory.NULL_KEY
    if isinstance(value, bool | int | float):
        return (1, value)
    if isinstance(value, str):
        return (2, value.casefold())
    return (3, _json_value(value)[0])


def _json_value(value: object) -> tuple[str, object]:
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, default=str)
        return encoded, json.loads(encoded)
    except (TypeError, ValueError):
        text = str(value)
        return json.dumps(text, ensure_ascii=False), text


@dataclass(frozen=True, slots=True)
class _Row:
    path: str
    values: dict[str, Any]
    record: CollectionRecord | None = None
    key: str = dc_field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _key(self.path))


@dataclass(frozen=True, slots=True)
class _Location:
    table: str
    row: _Row


class _Memory:
    def __init__(
        self,
        schema: TableSchema,
        rows: tuple[_Row, ...],
        locations: Mapping[str, _Location],
        generation: str,
        complete: bool,
    ) -> None:
        self._schema = schema
        self.rows = rows
        self.locations = locations
        self.generation = generation
        self.rows_cut = self.truncated = not complete
        self.sort_indexes: dict[str, array[int]] = {}
        self.lock = threading.Lock()
        self.fields = {field.name: field for field in schema.fields}

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def columns(self) -> tuple[TableField, ...]:
        return self._schema.fields

    @property
    def budget_check_rows(self) -> int:
        return memory.BUDGET_CHECK_ROWS

    def schema(self) -> TableSchema:
        return self._schema

    def _value(self, index: int, column: int) -> Any:
        return self.rows[index].values.get(self.columns[column].name)

    def is_null(self, index: int, column: int) -> bool:
        return self._value(index, column) is None

    def sort_key(self, index: int, column: int) -> memory.SortKey:
        return _sort(self._value(index, column))

    def text(self, index: int, column: int) -> str | None:
        value = self._value(index, column)
        return value if isinstance(value, str) else None

    def operand_key(self, column: int, raw: str) -> memory.SortKey:
        return _sort(coerce_filter_value(self.columns[column], raw))

    def cursor_key(self, column: int, rank: int, value: Any) -> memory.SortKey | None:
        if rank == 0:
            return memory.NULL_KEY
        return (rank, value) if rank in (1, 2, 3) and isinstance(value, str | int | float) else None

    def cells_per_row(self, names: Sequence[str]) -> int:
        return len(names)

    def cells(
        self,
        index: int,
        names: Sequence[str],
        *,
        max_chars: int | None = None,
        max_bytes: int | None = None,
    ) -> dict[str, Cell]:
        return self.cells_for(self.rows[index], names, max_chars=max_chars, max_bytes=max_bytes)

    def cells_for(
        self, row: _Row, names: Sequence[str], *, max_chars: int | None, max_bytes: int | None
    ) -> dict[str, Cell]:
        cells: dict[str, Cell] = {}
        for name in names:
            if name not in row.values:
                continue
            value = row.values[name]
            field = self.fields[name]
            if field.ref is not None and isinstance(value, str):
                location = self.locations.get(value)
                if location is not None and location.table == field.ref.table:
                    cells[name] = {
                        "ref": {
                            "table": location.table,
                            "key": location.row.key,
                            "label": _label(location.row),
                        }
                    }
                    continue
                cells[name] = {
                    "ref": {
                        "table": field.ref.table,
                        "key": None,
                        "label": value,
                        "missing": True,
                    }
                }
                continue
            cell = (
                text_cell(value, max_chars=max_chars, max_bytes=max_bytes)
                if isinstance(value, str)
                else value
            )
            if type(value) is int:
                cell = integer_cell(value)
            elif isinstance(value, float):
                cell = real_cell(value)
            if isinstance(value, dict | list):
                encoded, wire = _json_value(value)
                preview = text_cell(encoded, max_chars=max_chars, max_bytes=max_bytes)
                cell = {"json": wire, "preview": encoded} if isinstance(preview, str) else preview
            stored = _type(value)
            if (
                value is not None
                and field.type != "json"
                and stored != field.type
                and (stored, field.type)
                not in {("integer", "real"), ("text", "date"), ("text", "datetime")}
            ):
                cell = stored_cell(cell, stored)
            cells[name] = cell
        return cells

    def page_cells(
        self, indexes: Sequence[int], names: Sequence[str], *, max_chars: int
    ) -> list[dict[str, Cell]]:
        return [self.cells(index, names, max_chars=max_chars) for index in indexes]


def _label(row: _Row) -> str:
    for name in ("name", "title", "label", "id"):
        value = row.values.get(name)
        if isinstance(value, str) and value.strip():
            return value[:TABLE_CELL_PREVIEW_CHARS]
    return row.path


def _diagnostics(row: _Row) -> tuple[str, ...]:
    if row.record is None:
        return ()
    entries = [*row.record.errors, *row.record.repairs]
    return tuple(
        str(
            entry.get("message")
            or entry.get("code")
            or entry.get("kind")
            or "Record requires review"
        )[:TABLE_CELL_PREVIEW_CHARS]
        for entry in entries[:16]
    )


def _reserved(names: set[str], preferred: str) -> str:
    while preferred in names:
        preferred += "_"
    return preferred


def _group(snapshot: CollectionScan) -> dict[str, tuple[_Row, ...]]:
    records: dict[str, list[_Row]] = defaultdict(list)
    by_table: dict[str, list[CollectionRecord]] = defaultdict(list)
    ids: dict[str, list[str]] = defaultdict(list)
    problems: dict[str, list[str]] = defaultdict(list)
    source_records: dict[str, CollectionRecord] = {}
    for record in snapshot.records:
        source_records[record.path] = record
        if record.metadata is not None and record.values is not None:
            by_table[record.metadata.contract_id].append(record)
            identity = record.values.get("id")
            if isinstance(identity, str) and identity:
                ids[identity].append(record.path)
        for error in record.errors:
            problems[record.path].append(str(error.get("code") or error.get("kind") or "invalid"))
    for issue in snapshot.problems:
        problems[issue["path"]].append(issue["code"])
    for duplicates in ids.values():
        if len(duplicates) > 1:
            for path in duplicates:
                problems[path].append("duplicate_id")
    for path, issues in sorted(problems.items()):
        record = source_records.get(path)
        values = {"path": path, "problem": "; ".join(dict.fromkeys(issues))}
        if record is not None:
            values["state"] = record.state
        records[_PROBLEMS].append(_Row(path, values, record))
    for identity, group in by_table.items():
        names = {name for record in group for name in (record.values or {})}
        path_name = _reserved(names, "$path")
        state_name = _reserved(names, "$state")
        records[identity].extend(
            _Row(
                record.path,
                {**(record.values or {}), path_name: record.path, state_name: record.state},
                record,
            )
            for record in group
        )
    return {name: tuple(rows) for name, rows in sorted(records.items())}


def _locations(groups: Mapping[str, tuple[_Row, ...]]) -> dict[str, _Location]:
    found: dict[str, _Location] = {}
    ambiguous: set[str] = set()
    for table, rows in groups.items():
        if table == _PROBLEMS:
            continue
        for row in rows:
            identity = row.values.get("id")
            if isinstance(identity, str) and identity:
                if identity in found:
                    ambiguous.add(identity)
                found[identity] = _Location(table, row)
    return {identity: location for identity, location in found.items() if identity not in ambiguous}


def _schema(
    snapshot: CollectionScan, name: str, rows: tuple[_Row, ...], locations: Mapping[str, _Location]
) -> TableSchema:
    observed: dict[str, set[FieldType]] = defaultdict(set)
    targets: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        for field, value in row.values.items():
            kinds = observed[field]
            if value is not None:
                kinds.add(_type(value))
            if field != "id" and isinstance(value, str) and value in locations:
                targets[field].add(locations[value].table)
    descriptions: dict[str, FieldInfo] = {}
    bound_schemas = (
        {row.record.schema for row in rows if row.record is not None}
        if name != _PROBLEMS
        else set()
    )
    for definition in snapshot.schemas:
        if definition.path in bound_schemas:
            for info in definition.view().iter_fields(include_refs=False):
                descriptions.setdefault(info.name, info)
    fields: list[TableField] = []
    references: list[FieldRef] = []
    for field in dict.fromkeys([*descriptions, *observed]):
        info = descriptions.get(field)
        kinds = observed.get(field, set())
        inferred = next(iter(kinds)) if len(kinds) == 1 else "json"
        kind = _FIELD_TYPES.get(info.json_type or "", inferred) if info is not None else inferred
        if kind == "text" and info is not None:
            if info.format == "date":
                kind = "date"
            elif info.format == "date-time":
                kind = "datetime"
        destinations = targets.get(field, set())
        link = (
            FieldRef(next(iter(destinations)), (field,), ("id",))
            if len(destinations) == 1
            else None
        )
        if link is not None:
            references.append(link)
        fields.append(
            TableField(
                field,
                kind,
                title=info.title if info else None,
                format=info.format if info else None,
                enum=tuple(info.enum) if info and info.enum is not None else None,
                ref=link,
                sortable=True,
                filterable=kind != "json",
                numeric=kind in ("integer", "real"),
                description=info.description[:TABLE_CELL_PREVIEW_CHARS]
                if info and isinstance(info.description, str)
                else None,
            )
        )
    visible = [field.name for field in fields if not field.name.startswith("$path")]
    defaults = tuple(
        dict.fromkeys(
            [
                *[n for n in ("name", "title", "id", "$state") if n in visible],
                *[field.name for field in fields if field.name in visible and field.type != "json"],
                *visible,
            ]
        )
    )[:_PAGE_COLUMNS]
    return TableSchema(name, tuple(fields), (), defaults, tuple(references))


@dataclass(frozen=True, slots=True)
class _Projection:
    generation: str
    tables: dict[str, _Memory]

    @property
    def held_bytes(self) -> int:
        return sum(
            512 + 72 * len(row.values) for table in self.tables.values() for row in table.rows
        )


_PROJECTIONS = memory.MemoryCache[_Projection](
    max_entries=lambda: 16, max_bytes=lambda: 32 * 1024 * 1024
)


class CollectionSource:
    def __init__(self, handle: FolderTableHandle) -> None:
        self.root = collection_root(handle.path, handle.root)
        self.index = index_for(self.root, handle.root)
        self.folder = handle.path
        self.version = self.index.request(wait=INDEX_WAIT_SECONDS if handle.wait else None)

    def _projection(self, *, collection_wide: bool = False) -> _Projection:
        version = self.version
        snapshot = version.snapshot
        if snapshot is None:
            reason = (
                "The collection index could not be built."
                if version.failed
                else "The collection index is building."
            )
            raise SourceUnreadableError(reason)
        folder = self.root if collection_wide else self.folder
        prefix = folder.relative_to(self.root).as_posix()

        def build() -> _Projection:
            groups = _group(snapshot)
            locations = _locations(groups)
            tables: dict[str, _Memory] = {}
            for name, all_rows in groups.items():
                rows = tuple(
                    row for row in all_rows if prefix == "." or row.path.startswith(prefix + "/")
                )
                if rows:
                    schema = _schema(snapshot, name, all_rows, locations)
                    tables[name] = _Memory(
                        schema, rows, locations, version.generation, snapshot.complete
                    )
            return _Projection(version.generation, tables)

        return _PROJECTIONS.load(
            (self.index.served_root, self.root, folder), version.generation, build
        )

    def generation(self) -> str:
        return self.version.generation

    def tables(self) -> Sequence[TableInfo]:
        if self.version.snapshot is None:
            return ()
        tables = self._projection().tables
        titles = {name: _table_label(name) for name in tables}
        labels = Counter(titles.values())
        return tuple(
            TableInfo(
                name,
                titles[name] if labels[titles[name]] == 1 else name,
                "tables",
                True,
                len(table.rows),
            )
            for name, table in tables.items()
        )

    def _table(self, table: str) -> _Memory:
        found = self._projection().tables.get(table)
        if found is None:
            raise TableNotFoundError(f"{table!r} is not a collection table", table=table)
        return found

    def schema(self, table: str) -> TableSchema:
        return self._table(table).schema()

    def rows(self, table: str, query: TableQuery, budget: Budget) -> TablePage:
        model = self._table(table)
        ref = query.ref
        if ref is not None:
            relevant = tuple(
                row
                for row in model.rows
                if any(
                    ref.matches(relation)
                    and any(
                        isinstance(value := row.values.get(name), str)
                        and (location := model.locations.get(value)) is not None
                        and location.row.key == ref.key
                        for name in relation.fields
                    )
                    for relation in model.schema().references
                )
            )
            model = _Memory(
                model.schema(), relevant, model.locations, model.generation, not model.truncated
            )
        result = memory.page(model, query, budget)
        return replace(
            result,
            rows=tuple(
                replace(row, key=model.rows[cast(int, parse_position_key(row.key)) - 1].key)
                for row in result.rows
            ),
        )

    def _record(self, table: str, key: str) -> tuple[_Memory, _Row]:
        model = self._table(table)
        selected = next((row for row in model.rows if row.key == key), None)
        if selected is None:
            raise RecordNotFoundError(f"{key!r} is not a record of this table", key=key)
        return model, selected

    def record(self, table: str, key: str, budget: Budget) -> TableRecord:
        model, selected = self._record(table, key)
        identity = selected.values.get("id")
        incoming: list[BackrefCount] = []
        if isinstance(identity, str) and identity in model.locations:
            for name, candidate in self._projection(collection_wide=True).tables.items():
                for ref in candidate.schema().references:
                    if ref.table != table:
                        continue
                    count = sum(row.values.get(ref.fields[0]) == identity for row in candidate.rows)
                    if count:
                        incoming.append(
                            BackrefCount(
                                FieldRef(name, ref.fields, ref.to), count, not candidate.truncated
                            )
                        )
        cells = model.cells_for(
            selected, tuple(model.fields), max_chars=None, max_bytes=TABLE_RECORD_VALUE_BYTES
        )
        return TableRecord(
            key,
            cells,
            self.generation(),
            False,
            tuple(incoming),
            label=_label(selected),
            source_path=(self.root / selected.path).relative_to(self.index.served_root).as_posix()
            if selected.record is not None
            else None,
            diagnostics=_diagnostics(selected),
        )

    def card(self, table: str, key: str, budget: Budget) -> TableCard:
        model, selected = self._record(table, key)
        names = model.schema().default_columns[:TABLE_CARD_MAX_FIELDS]
        cells = model.cells_for(selected, names, max_chars=TABLE_CELL_PREVIEW_CHARS, max_bytes=None)
        return TableCard(key, _label(selected), cells, self.generation())


def adapter(handle: FolderTableHandle) -> CollectionSource:
    return CollectionSource(handle)


def _table_label(name: str) -> str:
    if name == _PROBLEMS:
        return "Problems"
    return name.partition(":")[2] or name
