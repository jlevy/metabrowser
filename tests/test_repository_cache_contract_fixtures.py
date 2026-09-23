"""Pin the repository-cache contracts frozen before the cache is implemented.

The fixtures under ``tests/fixtures/repository-cache/`` are the contract the
format-foundation and acquisition implementations consume: the root-argument URL grammar,
source and repository-store identity, slug derivation, Git version gates,
and the lock, publication, and staging-sweep state machines.

Rules with a production implementation replay the fixtures through it:
source and store identity, store keys, and slugs through
``metabrowser.cache.identity``, the root-argument URL grammar through
``metabrowser.cache.urls``, the Git version gates through
``metabrowser.git.process``, and the lock hierarchy, lock-file placement, and lock
sequences through ``metabrowser.cache.locks``. The sweep machine replays against
``metabrowser.cache.reclaim`` in ``tests/test_cache_reclaim.py``, and
``tests/test_cache_publish.py`` checks the locks the real acquisition holds against the
acquisition machine.

The state-machine well-formedness checks verify the design itself.
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator

from metabrowser.cache import identity, locks, urls
from metabrowser.cache.locks import HIERARCHY_RANKS, LockKind, LockOrder, LockOrderError
from metabrowser.git import process as git_process
from metabrowser.home import ensure_home

FIXTURES = Path(__file__).parent / "fixtures" / "repository-cache"


def _load(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((FIXTURES / name).read_text(encoding="utf-8")))


@pytest.mark.parametrize(
    ("fixture", "schema_name"),
    [
        ("url-grammar.json", "url-grammar.schema.json"),
        ("source-identity.json", "source-identity.schema.json"),
        ("git-version-gates.json", "git-version-gates.schema.json"),
        ("state-machines.json", "state-machines.schema.json"),
    ],
)
def test_fixture_matches_its_schema(fixture: str, schema_name: str) -> None:
    schema = _load(schema_name)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(_load(fixture))


# ----------------------------------------------------------------------------
# URL grammar: replayed through metabrowser.cache.urls


def _outcome(value: str, defaults: dict[str, str]) -> dict[str, str]:
    return urls.classification_as_fixture(urls.classify_root_argument(value, defaults=defaults))


def test_url_grammar_cases_have_one_frozen_outcome() -> None:
    grammar = _load("url-grammar.json")
    defaults = cast(dict[str, str], grammar["default_ports"])
    assert defaults == urls.DEFAULT_PORTS
    assert set(grammar["transports"]) == urls.GIT_SOURCE_SCHEMES
    ids = [case["id"] for case in grammar["cases"]]
    assert len(ids) == len(set(ids))
    mismatches = {
        case["id"]: (_outcome(case["input"], defaults), case["expected"])
        for case in grammar["cases"]
        if _outcome(case["input"], defaults) != case["expected"]
    }
    assert mismatches == {}


def test_url_grammar_reasons_are_closed_and_exercised() -> None:
    grammar = _load("url-grammar.json")
    declared = set(grammar["reasons"])
    used = {
        case["expected"]["reason"]
        for case in grammar["cases"]
        if case["expected"]["outcome"] == "rejected"
    }
    assert used <= declared
    assert declared - used == set()
    outcomes = {case["expected"]["outcome"] for case in grammar["cases"]}
    assert outcomes == {"git_source", "local_path", "rejected"}
    transports = {
        case["expected"]["transport"]
        for case in grammar["cases"]
        if case["expected"]["outcome"] == "git_source"
    }
    assert transports == set(grammar["transports"])


def test_url_grammar_normalization_is_idempotent_and_credential_free() -> None:
    grammar = _load("url-grammar.json")
    defaults = cast(dict[str, str], grammar["default_ports"])
    for case in grammar["cases"]:
        expected = case["expected"]
        if expected["outcome"] != "git_source":
            continue
        normalized = expected["normalized"]
        assert _outcome(normalized, defaults) == expected, case["id"]
        assert "?" not in normalized and "#" not in normalized
        if expected["transport"] == "https":
            assert "@" not in normalized.split("/", 3)[2]


# ----------------------------------------------------------------------------
# Source identity, store identity, and slugs: replayed through metabrowser.cache.identity


def test_the_identity_specification_matches_the_production_constants() -> None:
    document = _load("source-identity.json")
    assert document["source_identity"]["domain"] == identity.SOURCE_IDENTITY_DOMAIN
    assert document["store_identity"]["domain"] == identity.STORE_IDENTITY_DOMAIN
    assert document["store_identity"]["key_hex_digits"] == identity.STORE_KEY_HEX_DIGITS
    slug_spec = document["slug"]
    assert slug_spec["token_separator"] == identity.SLUG_TOKEN_SEPARATOR
    assert slug_spec["readable_max_bytes"] == identity.SLUG_READABLE_MAX_BYTES
    assert slug_spec["empty_readable"] == identity.SLUG_EMPTY_READABLE
    assert tuple(slug_spec["suffix_hex_digits"]) == identity.SLUG_SUFFIX_HEX_DIGITS
    assert slug_spec["max_bytes"] == identity.SLUG_MAX_BYTES


def test_source_identity_and_slugs_are_reproducible() -> None:
    document = _load("source-identity.json")
    grammar = _load("url-grammar.json")
    defaults = cast(dict[str, str], grammar["default_ports"])
    for record in document["sources"]:
        classified = _outcome(record["input"], defaults)
        assert classified["normalized"] == record["normalized"], record["input"]
        assert classified["transport"] == record["transport"]
        assert classified["form"] == record["form"]
        source = identity.source_identity(record["transport"], record["normalized"])
        assert record["source_id"] == source
        slug = identity.cache_slug(
            record["transport"], record["normalized"], source, slug_owner=lambda _slug: None
        )
        assert record["slug"] == slug
        assert identity.is_slug(slug)
        assert identity.slug_matches_identity(slug, source)
        assert len(slug.encode()) <= document["slug"]["max_bytes"]
        for object_format, store in record["generic_stores"].items():
            store_id = identity.repository_store_id(source, object_format)
            assert store["store_id"] == store_id
            assert store["store_key"] == identity.store_key(store_id)


def test_identity_equivalence_classes_follow_the_grammar() -> None:
    document = _load("source-identity.json")
    defaults = cast(dict[str, str], _load("url-grammar.json")["default_ports"])
    for group in document["equivalence"]:
        ids = {
            identity.source_identity(
                cast(identity.GitTransport, _outcome(value, defaults)["transport"]),
                _outcome(value, defaults)["normalized"],
            )
            for value in group["inputs"]
        }
        assert (len(ids) == 1) is group["same_source"], group["why"]


def test_slug_collisions_extend_the_suffix_deterministically() -> None:
    document = _load("source-identity.json")
    by_normalized = {record["normalized"]: record for record in document["sources"]}
    for collision in document["slug_collisions"]:
        record = by_normalized[collision["normalized"]]
        existing = cast(dict[str, str], collision["existing"])
        slug = identity.cache_slug(
            record["transport"],
            record["normalized"],
            record["source_id"],
            slug_owner=existing.get,
        )
        assert slug == collision["expected_slug"], collision["why"]


def test_every_claimed_suffix_width_is_a_typed_collision() -> None:
    record = _load("source-identity.json")["sources"][0]
    digest = record["source_id"].removeprefix("sha256:")
    readable = identity.slug_readable_part(record["transport"], record["normalized"])
    claimed = {
        f"{readable}--{digest[:width]}": "sha256:" + "0" * 64
        for width in identity.SLUG_SUFFIX_HEX_DIGITS
    }
    with pytest.raises(identity.SlugCollisionError):
        identity.cache_slug(
            record["transport"], record["normalized"], record["source_id"], slug_owner=claimed.get
        )


def test_provider_store_identity_is_domain_separated() -> None:
    document = _load("source-identity.json")
    generic_ids = {
        store["store_id"]
        for record in document["sources"]
        for store in record["generic_stores"].values()
    }
    for record in document["provider_stores"]:
        expected = identity.provider_repository_store_id(
            record["provider_kind"],
            record["provider_instance"],
            record["repository_opaque_id"],
            record["object_format"],
        )
        assert record["store_id"] == expected
        assert record["store_key"] == identity.store_key(expected)
        assert expected not in generic_ids
    keys = [
        store["store_key"]
        for record in document["sources"]
        for store in record["generic_stores"].values()
    ] + [record["store_key"] for record in document["provider_stores"]]
    assert len(keys) == len(set(keys))


# ----------------------------------------------------------------------------
# Git version gates: replayed through metabrowser.git.process


def test_acquisition_floor_constants_match_the_fixture() -> None:
    gates = _load("git-version-gates.json")
    (acquisition,) = gates["gates"]
    assert list(git_process.ACQUISITION_MINIMUM) == acquisition["minimum"]
    assert {
        track: list(version) for track, version in git_process.ACQUISITION_PATCHED_TRACKS.items()
    } == acquisition["patched_tracks"]
    assert list(git_process.ACQUISITION_NEWEST_PATCHED) == acquisition["newest_patched"]


def test_git_version_gates_decide_every_case() -> None:
    gates = _load("git-version-gates.json")
    for case in gates["cases"]:
        assert (
            git_process.parsed_git_version_as_fixture(case["version_output"]) == case["parsed"]
        ), case["version_output"]
        assert (
            git_process.acquisition_gate_as_fixture(case["version_output"]) == case["expected"]
        ), case["version_output"]


# ----------------------------------------------------------------------------
# Lock hierarchy: replayed through metabrowser.cache.locks


def _lock_sequence_valid(steps: list[str]) -> bool:
    """Replay one fixture sequence through the production lock-order state machine."""

    order = LockOrder()
    held: list[tuple[LockKind, str | None]] = []
    kinds = {kind.value: kind for kind in HIERARCHY_RANKS}
    try:
        for step in steps:
            if step == "network":
                order.check_network("network work")
                continue
            if step.startswith("release:"):
                name = step.removeprefix("release:")
                matches = [item for item in held if item[0].value == name]
                if not matches:
                    return False
                held.remove(matches[-1])
                order.released(*matches[-1])
                continue
            name, _, key = step.partition(":")
            kind = kinds.get(name)
            if kind is None:
                return False
            order.check(kind, key or None, blocking=True)
            order.acquired(kind, key or None)
            held.append((kind, key or None))
    except LockOrderError:
        return False
    return True


def _store_key(key: str) -> str:
    """A 64-digit store key that sorts like the fixture's placeholder key."""

    return key.encode().hex().rjust(64, "0")[-64:]


def _real_lock(home: Path, kind: LockKind, key: str | None) -> locks.CacheLock:
    if kind is LockKind.HOME:
        return locks.application_home_lock(home)
    if kind is LockKind.SOURCE_ALIAS:
        assert key is not None
        return locks.source_alias_lock(home, key)
    if kind is LockKind.REPOSITORY_STORE:
        assert key is not None
        return locks.repository_store_lock(home, _store_key(key))
    assert key is not None
    return locks.provider_resource_lock(home, key)


def test_the_hierarchy_matches_the_production_ranks() -> None:
    hierarchy = _load("state-machines.json")["locks"]["hierarchy"]
    assert [lock["rank"] for lock in hierarchy] == sorted({lock["rank"] for lock in hierarchy})
    assert {LockKind(lock["name"]): lock["rank"] for lock in hierarchy} == HIERARCHY_RANKS
    side = {lock["name"] for lock in _load("state-machines.json")["locks"]["side_locks"]}
    assert side | {lock["name"] for lock in hierarchy} == {kind.value for kind in LockKind}


def test_lock_sequences_follow_the_frozen_order() -> None:
    for sequence in _load("state-machines.json")["locks"]["sequences"]:
        assert _lock_sequence_valid(sequence["steps"]) is sequence["valid"], sequence["id"]


def test_lock_sequences_replay_with_real_locks(tmp_path: Path) -> None:
    home = tmp_path / "home"
    ensure_home(home)
    kinds = {kind.value: kind for kind in HIERARCHY_RANKS}
    for sequence in _load("state-machines.json")["locks"]["sequences"]:
        held: list[locks.CacheLock] = []
        refused = False
        try:
            for step in sequence["steps"]:
                if step == "network":
                    locks.require_no_hierarchy_locks("network work")
                elif step.startswith("release:"):
                    name = step.removeprefix("release:")
                    lock = next(lock for lock in reversed(held) if lock.kind.value == name)
                    held.remove(lock)
                    lock.release()
                else:
                    name, _, key = step.partition(":")
                    if name not in kinds:
                        refused = True
                        break
                    held.append(_real_lock(home, kinds[name], key or None))
        except LockOrderError:
            refused = True
        finally:
            for lock in reversed(held):
                lock.release()
        assert refused is not sequence["valid"], sequence["id"]
        assert locks.held_locks() == (), sequence["id"]


def test_lock_files_are_where_the_fixture_places_them(tmp_path: Path) -> None:
    home = tmp_path / "home"
    ensure_home(home)
    document = _load("state-machines.json")["locks"]
    templates = {
        lock["name"]: lock["path"] for lock in [*document["hierarchy"], *document["side_locks"]]
    }
    slug = "github-com--pallets--flask--e7b7fe0ffe8a"
    store = "4c2d8559cb0179baca3afa2f633e1cfd7271b82e4fb7f0c451dfa9354aa70aff"
    acquisitions = {
        "home": (lambda: locks.application_home_lock(home), {}),
        "source_alias": (lambda: locks.source_alias_lock(home, slug), {"<slug>": slug}),
        "repository_store": (
            lambda: locks.repository_store_lock(home, store),
            {"<store-key>": store},
        ),
        "staging_entry": (lambda: locks.staging_entry_lock(home, "e1"), {"<entry>": "e1"}),
    }
    for name, (acquire, placeholders) in acquisitions.items():
        expected = templates[name]
        for placeholder, value in placeholders.items():
            expected = expected.replace(placeholder, value)
        with acquire() as lock:
            assert lock.relative_path == expected, name
            assert lock.path.is_file(), name
    # The provider plan owns the provider/resource spelling; only its rank is frozen here.
    assert templates["provider_resource"] == "owned by the provider storage plan"


# ----------------------------------------------------------------------------
# State machines


def test_state_machines_are_well_formed() -> None:
    document = _load("state-machines.json")
    hierarchy = document["locks"]["hierarchy"]
    lock_names = {lock["name"] for lock in hierarchy} | {
        lock["name"] for lock in document["locks"]["side_locks"]
    }
    recoveries = set(document["crash_recovery"])
    for machine in document["machines"]:
        states = {state["name"]: state for state in machine["states"]}
        assert len(states) == len(machine["states"]), machine["name"]
        assert machine["initial"] in states
        outgoing: dict[str, list[dict[str, Any]]] = {name: [] for name in states}
        for transition in machine["transitions"]:
            assert transition["from"] in states, (machine["name"], transition)
            assert transition["to"] in states, (machine["name"], transition)
            assert set(transition["holds"]) <= lock_names, (machine["name"], transition)
            if transition.get("network"):
                ordered = [
                    lock for lock in transition["holds"] if lock in {h["name"] for h in hierarchy}
                ]
                assert ordered == [], (machine["name"], transition["event"])
            ordered_steps = [
                lock for lock in transition["holds"] if lock in {h["name"] for h in hierarchy}
            ]
            ranks = [
                next(h["rank"] for h in hierarchy if h["name"] == lock) for lock in ordered_steps
            ]
            assert ranks == sorted(ranks), (machine["name"], transition["event"])
            outgoing[transition["from"]].append(transition)
        for name, state in states.items():
            if state["terminal"]:
                assert outgoing[name] == [], (machine["name"], name)
            else:
                assert outgoing[name], (machine["name"], name)
                assert state["on_crash"] in recoveries, (machine["name"], name)
        reachable = {machine["initial"]}
        queue = deque([machine["initial"]])
        while queue:
            current = queue.popleft()
            for transition in outgoing[current]:
                if transition["to"] not in reachable:
                    reachable.add(transition["to"])
                    queue.append(transition["to"])
        assert reachable == set(states), (machine["name"], set(states) - reachable)


def test_state_machine_scenarios_replay() -> None:
    document = _load("state-machines.json")
    machines = {machine["name"]: machine for machine in document["machines"]}
    recoveries = document["crash_recovery"]
    for scenario in document["scenarios"]:
        machine = machines[scenario["machine"]]
        states = {state["name"]: state for state in machine["states"]}
        current = machine["initial"]
        visible = states[current]["visible"]
        crashed = False
        for event in scenario["events"]:
            assert not crashed, (scenario["id"], "events after crash")
            if event == "crash":
                recovery = cast(str, states[current]["on_crash"])
                after = recoveries[recovery]["visible_after"]
                visible = states[current]["visible"] if after == "unchanged" else after
                current = recovery
                crashed = True
                continue
            candidates = [
                transition
                for transition in machine["transitions"]
                if transition["from"] == current and transition["event"] == event
            ]
            assert len(candidates) == 1, (scenario["id"], current, event)
            current = candidates[0]["to"]
            visible = states[current]["visible"]
        assert current == scenario["expected_final"], scenario["id"]
        assert visible is scenario["expected_visible"], scenario["id"]


def test_every_machine_has_a_crash_scenario_or_is_crash_free() -> None:
    document = _load("state-machines.json")
    crashing = {
        scenario["machine"] for scenario in document["scenarios"] if "crash" in scenario["events"]
    }
    for machine in document["machines"]:
        recoveries = {
            state.get("on_crash") for state in machine["states"] if not state["terminal"]
        } - {"nothing_to_recover", "sweep_restarts"}
        if recoveries:
            assert machine["name"] in crashing, machine["name"]
