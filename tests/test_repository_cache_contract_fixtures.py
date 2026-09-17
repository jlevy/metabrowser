"""Pin the repository-cache contracts frozen before the cache is implemented.

The fixtures under ``tests/fixtures/repository-cache/`` are the contract the
format-foundation and acquisition implementations consume: the root-argument URL grammar,
source and repository-store identity, slug derivation, Git version gates,
and the lock, publication, lease, trash, and quarantine state machines.

No production module implements them yet, so each test carries a small
reference oracle written from the fixture's own prose rules. The oracle
proves the frozen rules are complete and consistent: every case has exactly
one outcome, every declared reason is exercised, identities are reproducible
from their declared material, and every state machine is well formed. When
``metabrowser.cache.urls``, ``metabrowser.cache.identity``, and the Git
version gate land, their tests must replay these same fixtures against the
production functions; the oracle here is a specification aid, not a second
implementation to keep.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import string
from collections import deque
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote_to_bytes

import pytest
from jsonschema import Draft202012Validator

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
        ("object-requests.json", "object-requests.schema.json"),
    ],
)
def test_fixture_matches_its_schema(fixture: str, schema_name: str) -> None:
    schema = _load(schema_name)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(_load(fixture))


# ----------------------------------------------------------------------------
# URL grammar oracle


class Rejected(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


_SCHEME = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*)://")
_HELPER = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*::")
_MALFORMED = re.compile(r"^(?:https|ssh|file|http|git):(?!//)", re.IGNORECASE)
_SCP = re.compile(
    r"^(?P<user>[^@/:\[\]]+)@(?P<host>\[[^\]/]*\]|[^/:\[\]]*):(?P<path>.*)$", re.DOTALL
)
_LABEL = r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
_REG_NAME = re.compile(rf"^{_LABEL}(?:\.{_LABEL})*$")
_IPV6 = re.compile(r"^\[[0-9a-f:.]+\]$")
_USER = re.compile(r"^[A-Za-z0-9._~-]+$")
_UNRESERVED = frozenset(string.ascii_letters + string.digits + "-._~")
_PCHAR = _UNRESERVED | frozenset("!$&'()*+,;=:@")
_HEX = frozenset(string.hexdigits)


def _common_checks(value: str) -> None:
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F or ch.isspace() for ch in value):
        raise Rejected("control_or_whitespace")
    if any(ord(ch) > 0x7F for ch in value):
        raise Rejected("non_ascii")
    if "\\" in value:
        raise Rejected("backslash")
    if "?" in value:
        raise Rejected("query_not_allowed")
    if "#" in value:
        raise Rejected("fragment_not_allowed")


def _host(host: str) -> str:
    if host == "":
        raise Rejected("missing_host")
    if host.startswith("-"):
        raise Rejected("option_like")
    folded = host.lower()
    pattern = _IPV6 if folded.startswith("[") else _REG_NAME
    if not pattern.match(folded):
        raise Rejected("invalid_host")
    return folded


def _user(user: str) -> str:
    if user.startswith("-"):
        raise Rejected("option_like")
    if not _USER.match(user):
        raise Rejected("invalid_user")
    return user


def _segment(segment: str, *, percent: bool) -> str:
    out: list[str] = []
    index = 0
    while index < len(segment):
        ch = segment[index]
        if ch == "%":
            if not percent:
                raise Rejected("invalid_path_character")
            digits = segment[index + 1 : index + 3]
            if len(digits) != 2 or not set(digits) <= _HEX:
                raise Rejected("invalid_percent_encoding")
            byte = int(digits, 16)
            if byte <= 0x20 or byte == 0x7F:
                raise Rejected("control_or_whitespace")
            if chr(byte) in "/\\":
                raise Rejected("encoded_delimiter")
            out.append(chr(byte) if chr(byte) in _UNRESERVED else "%" + digits.upper())
            index += 3
            continue
        if ch not in _PCHAR:
            raise Rejected("invalid_path_character")
        out.append(ch)
        index += 1
    result = "".join(out)
    if result in {".", ".."}:
        raise Rejected("dot_segment")
    return result


def _path(path: str, *, strip_trailing: bool, percent: bool) -> str:
    segments = path.split("/")
    leading = segments[0] == ""
    if leading:
        segments = segments[1:]
    if segments and segments[-1] == "" and strip_trailing:
        segments = segments[:-1]
    trailing = bool(segments) and segments[-1] == ""
    body = segments[:-1] if trailing else segments
    if not body:
        raise Rejected("missing_repository_path")
    if any(segment == "" for segment in body):
        raise Rejected("empty_path_segment")
    normalized = [_segment(segment, percent=percent) for segment in body]
    return ("/" if leading else "") + "/".join(normalized) + ("/" if trailing else "")


def classify(value: str, defaults: dict[str, str]) -> dict[str, str]:
    """The frozen root-argument grammar, in the fixture's declared check order."""
    if value == "":
        raise Rejected("empty")
    if value.startswith("-"):
        raise Rejected("option_like")
    if _HELPER.match(value):
        raise Rejected("remote_helper_syntax")
    scheme_match = _SCHEME.match(value)
    if scheme_match is None:
        if _MALFORMED.match(value):
            raise Rejected("malformed_url")
        scp = _SCP.match(value)
        if scp is None:
            return {"outcome": "local_path"}
        _common_checks(value)
        user = _user(scp.group("user"))
        host = _host(scp.group("host"))
        path = scp.group("path")
        if path.startswith("-"):
            raise Rejected("option_like")
        if path in {"", "/"}:
            raise Rejected("missing_repository_path")
        normalized_path = _path(path, strip_trailing=False, percent=False)
        return {
            "outcome": "git_source",
            "transport": "ssh",
            "form": "scp",
            "normalized": f"{user}@{host}:{normalized_path}",
        }
    scheme = scheme_match.group(1).lower()
    if scheme not in {"https", "ssh", "file"}:
        raise Rejected("unsupported_transport")
    _common_checks(value)
    rest = value[scheme_match.end() :]
    authority, slash, tail = rest.partition("/")
    path = slash + tail
    userinfo: str | None = None
    hostport = authority
    if "@" in authority:
        userinfo, _, hostport = authority.rpartition("@")
    if scheme == "file":
        if userinfo is not None or hostport.lower() not in {"", "localhost"}:
            raise Rejected("file_authority_not_local")
        prefix = "file://"
    else:
        if userinfo is not None and (scheme == "https" or ":" in userinfo):
            raise Rejected("credentials_in_url")
        user = _user(userinfo) if userinfo is not None else None
        if hostport.startswith("["):
            close = hostport.find("]")
            if close < 0:
                raise Rejected("invalid_host")
            host_text, after = hostport[: close + 1], hostport[close + 1 :]
            if after and not after.startswith(":"):
                raise Rejected("invalid_host")
            port: str | None = after[1:] if after else None
        else:
            host_text, separator, port_text = hostport.partition(":")
            port = port_text if separator else None
        host = _host(host_text)
        if port == "":
            port = None
        if port is not None:
            if not (port.isascii() and port.isdigit()) or port.startswith("0"):
                raise Rejected("invalid_port")
            if not 1 <= int(port) <= 65535:
                raise Rejected("invalid_port")
            if port == defaults[scheme]:
                port = None
        prefix = f"{scheme}://" + (f"{user}@" if user else "") + host + (f":{port}" if port else "")
    if path in {"", "/"}:
        raise Rejected("missing_repository_path")
    normalized_path = _path(path, strip_trailing=scheme != "ssh", percent=True)
    return {
        "outcome": "git_source",
        "transport": scheme,
        "form": "url",
        "normalized": prefix + normalized_path,
    }


def _outcome(value: str, defaults: dict[str, str]) -> dict[str, str]:
    try:
        return classify(value, defaults)
    except Rejected as rejected:
        return {"outcome": "rejected", "reason": rejected.reason}


def test_url_grammar_cases_have_one_frozen_outcome() -> None:
    grammar = _load("url-grammar.json")
    defaults = cast(dict[str, str], grammar["default_ports"])
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
        assert classify(normalized, defaults) == expected, case["id"]
        assert "?" not in normalized and "#" not in normalized
        if expected["transport"] == "https":
            assert "@" not in normalized.split("/", 3)[2]


# ----------------------------------------------------------------------------
# Source identity, store identity, and slugs


def _digest(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def source_id(spec: dict[str, Any], transport: str, normalized: str) -> str:
    return "sha256:" + _digest(f"{spec['domain']}\0{transport}\0{normalized}")


def generic_store_id(spec: dict[str, Any], source: str, object_format: str) -> str:
    return "sha256:" + _digest(f"{spec['domain']}\0source\0{source}\0{object_format}")


def provider_store_id(spec: dict[str, Any], record: dict[str, str]) -> str:
    material = "\0".join(
        [
            spec["domain"],
            "provider",
            record["provider_kind"],
            record["provider_instance"],
            record["repository_opaque_id"],
            record["object_format"],
        ]
    )
    return "sha256:" + _digest(material)


def _fold(token: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", token.lower()).strip("-")


def slug_tokens(transport: str, form: str, normalized: str) -> list[str]:
    if form == "scp":
        user_host, _, path = normalized.partition(":")
        host = user_host.rpartition("@")[2]
        raw = [host, *path.split("/")]
    elif transport == "file":
        segments = [segment for segment in normalized[len("file://") :].split("/") if segment]
        raw = ["local", segments[-1]]
    else:
        rest = normalized.split("://", 1)[1]
        authority, _, path = rest.partition("/")
        hostport = authority.rpartition("@")[2]
        raw = [
            hostport.replace(":", "-") if not hostport.startswith("[") else hostport,
            *path.split("/"),
        ]
    segments = [segment for segment in raw if segment]
    if len(segments) > 1 and segments[-1].endswith(".git") and segments[-1] != ".git":
        segments[-1] = segments[-1][: -len(".git")]
    decoded = [unquote_to_bytes(segment).decode("utf-8", errors="replace") for segment in segments]
    return [folded for folded in (_fold(token) for token in decoded) if folded]


def cache_slug(
    spec: dict[str, Any],
    transport: str,
    form: str,
    normalized: str,
    digest: str,
    existing: dict[str, str],
) -> str:
    readable = spec["token_separator"].join(slug_tokens(transport, form, normalized))
    readable = readable or spec["empty_readable"]
    if len(readable) > spec["readable_max_bytes"]:
        readable = readable[: spec["readable_max_bytes"]].rstrip("-")
    identity = "sha256:" + digest
    for width in spec["suffix_hex_digits"]:
        candidate = f"{readable}{spec['token_separator']}{digest[:width]}"
        owner = existing.get(candidate)
        if owner is None or owner == identity:
            return candidate
    raise AssertionError("every suffix width collided")


def test_source_identity_and_slugs_are_reproducible() -> None:
    identity = _load("source-identity.json")
    grammar = _load("url-grammar.json")
    defaults = cast(dict[str, str], grammar["default_ports"])
    source_spec = identity["source_identity"]
    store_spec = identity["store_identity"]
    slug_spec = identity["slug"]
    for record in identity["sources"]:
        classified = classify(record["input"], defaults)
        assert classified["normalized"] == record["normalized"], record["input"]
        assert classified["transport"] == record["transport"]
        assert classified["form"] == record["form"]
        expected_source = source_id(source_spec, record["transport"], record["normalized"])
        assert record["source_id"] == expected_source
        digest = expected_source.removeprefix("sha256:")
        slug = cache_slug(
            slug_spec, record["transport"], record["form"], record["normalized"], digest, {}
        )
        assert record["slug"] == slug
        assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*(?:--[a-z0-9]+(?:-[a-z0-9]+)*)*", slug)
        assert len(slug.encode()) <= slug_spec["max_bytes"]
        for object_format, store in record["generic_stores"].items():
            expected_store = generic_store_id(store_spec, expected_source, object_format)
            assert store["store_id"] == expected_store
            assert (
                store["store_key"]
                == expected_store.removeprefix("sha256:")[: store_spec["key_hex_digits"]]
            )


def test_identity_equivalence_classes_follow_the_grammar() -> None:
    identity = _load("source-identity.json")
    defaults = cast(dict[str, str], _load("url-grammar.json")["default_ports"])
    for group in identity["equivalence"]:
        ids = {
            source_id(
                identity["source_identity"],
                classify(value, defaults)["transport"],
                classify(value, defaults)["normalized"],
            )
            for value in group["inputs"]
        }
        assert (len(ids) == 1) is group["same_source"], group["why"]


def test_slug_collisions_extend_the_suffix_deterministically() -> None:
    identity = _load("source-identity.json")
    by_normalized = {record["normalized"]: record for record in identity["sources"]}
    for collision in identity["slug_collisions"]:
        record = by_normalized[collision["normalized"]]
        digest = record["source_id"].removeprefix("sha256:")
        slug = cache_slug(
            identity["slug"],
            record["transport"],
            record["form"],
            record["normalized"],
            digest,
            collision["existing"],
        )
        assert slug == collision["expected_slug"], collision["why"]


def test_provider_store_identity_is_domain_separated() -> None:
    identity = _load("source-identity.json")
    store_spec = identity["store_identity"]
    generic_ids = {
        store["store_id"]
        for record in identity["sources"]
        for store in record["generic_stores"].values()
    }
    for record in identity["provider_stores"]:
        expected = provider_store_id(store_spec, record)
        assert record["store_id"] == expected
        assert (
            record["store_key"] == expected.removeprefix("sha256:")[: store_spec["key_hex_digits"]]
        )
        assert expected not in generic_ids
    keys = [
        store["store_key"]
        for record in identity["sources"]
        for store in record["generic_stores"].values()
    ] + [record["store_key"] for record in identity["provider_stores"]]
    assert len(keys) == len(set(keys))


# ----------------------------------------------------------------------------
# Git version gates


_VERSION = re.compile(r"^git version (\d+)\.(\d+)(?:\.(\d+))?")


def parse_git_version(text: str) -> tuple[int, int, int] | None:
    match = _VERSION.match(text)
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3) or 0))


def _meets(version: tuple[int, int, int] | None, gate: dict[str, Any]) -> bool:
    if version is None:
        return False
    minimum = tuple(gate["minimum"])
    if version < minimum:
        return False
    tracks = cast(dict[str, list[int]], gate.get("patched_tracks", {}))
    if not tracks:
        return True
    track = f"{version[0]}.{version[1]}"
    if track in tracks:
        return version >= tuple(tracks[track])
    return version >= tuple(gate["newest_patched"])


def test_git_version_gates_decide_every_case() -> None:
    gates = _load("git-version-gates.json")
    (acquisition,) = gates["gates"]
    for case in gates["cases"]:
        version = parse_git_version(case["version_output"])
        expected_version = case["parsed"]
        assert (list(version) if version else None) == expected_version, case["version_output"]
        admitted = _meets(version, acquisition)
        assert {
            "acquisition": admitted,
            "initial_strategy_for_https": "blobless" if admitted else "refused",
        } == case["expected"], case["version_output"]


def test_every_admitted_git_carries_the_lazy_fetch_guard() -> None:
    gates = _load("git-version-gates.json")
    (acquisition,) = gates["gates"]
    guard = gates["lazy_fetch_guard"]

    def tag(value: str) -> tuple[int, int, int]:
        parsed = parse_git_version(f"git version {value.removeprefix('v')}")
        assert parsed is not None
        return parsed

    present = [tag(value) for value in guard["verified_present"]]
    absent = [tag(value) for value in guard["verified_absent"]]
    newest_unguarded_track = max((version[0], version[1]) for version in absent)
    for track, floor in acquisition["patched_tracks"].items():
        major, minor = (int(part) for part in track.split("."))
        floor_version = (floor[0], floor[1], floor[2])
        assert not any(version == floor_version for version in absent), track
        guarded_on_track = [
            version for version in present if (version[0], version[1]) == (major, minor)
        ]
        if guarded_on_track:
            assert min(guarded_on_track) <= floor_version, track
        else:
            assert (major, minor) > newest_unguarded_track, track


# ----------------------------------------------------------------------------
# Object requests: change-set classification and rejection splitting


def classify_change_set(
    spec: dict[str, Any], entries: list[dict[str, str]]
) -> dict[str, list[str]]:
    kinds = cast(dict[str, str], spec["change_set"]["modes"])
    result: dict[str, list[str]] = {"request": [], "submodules": [], "unsupported": []}
    for entry in entries:
        oid = entry["oid"]
        if set(oid) == {"0"}:
            continue
        kind = kinds.get(entry["mode"])
        bucket = {"blob": "request", "submodule": "submodules"}.get(kind or "", "unsupported")
        if kind == "tree":
            continue
        if oid not in result[bucket]:
            result[bucket].append(oid)
    return result


class JobFailed(Exception):
    pass


def split_request(
    spec: dict[str, Any], wants: list[str], rejected_by_server: set[str], failure_class: str
) -> dict[str, Any]:
    sizes: list[int] = []
    accepted: list[str] = []
    rejected: list[str] = []

    def attempt(oids: list[str]) -> None:
        sizes.append(len(oids))
        if not rejected_by_server.intersection(oids):
            accepted.extend(oids)
            return
        if failure_class not in spec["request"]["per_object_rejections"]:
            raise JobFailed(failure_class)
        if len(oids) == 1:
            rejected.extend(oids)
            return
        middle = (len(oids) + 1) // 2
        attempt(oids[:middle])
        attempt(oids[middle:])

    try:
        attempt(wants)
    except JobFailed:
        return {"outcome": "job_failed", "accepted": [], "rejected": [], "request_sizes": sizes}
    outcome = "partial" if rejected else "complete"
    return {"outcome": outcome, "accepted": accepted, "rejected": rejected, "request_sizes": sizes}


def test_change_sets_request_only_blob_modes() -> None:
    spec = _load("object-requests.json")
    assert {mode for mode, kind in spec["change_set"]["modes"].items() if kind == "blob"} == {
        "100644",
        "100755",
        "120000",
    }
    for case in spec["classification_cases"]:
        assert classify_change_set(spec, case["entries"]) == case["expected"], case["id"]


def test_rejected_requests_split_to_single_object_ids() -> None:
    spec = _load("object-requests.json")
    classes = set(spec["request"]["per_object_rejections"]) | set(
        spec["request"]["terminal_failures"]
    )
    for case in spec["request_cases"]:
        assert case["failure_class"] in classes, case["id"]
        result = split_request(
            spec, case["wants"], set(case["rejected_by_server"]), case["failure_class"]
        )
        assert result == case["expected"], case["id"]
        rejected = len(case["rejected_by_server"]) if result["outcome"] != "job_failed" else 0
        bound = 1 + 2 * rejected * max(1, math.ceil(math.log2(max(len(case["wants"]), 1))))
        assert len(result["request_sizes"]) <= bound, case["id"]


# ----------------------------------------------------------------------------
# Lock hierarchy and state machines


def _lock_sequence_valid(hierarchy: list[dict[str, Any]], steps: list[str]) -> bool:
    ranks = {lock["name"]: lock["rank"] for lock in hierarchy}
    multiple = {lock["name"] for lock in hierarchy if lock["multiple"]}
    held: list[tuple[int, str]] = []
    for step in steps:
        if step == "network":
            if held:
                return False
            continue
        if step.startswith("release:"):
            name = step.removeprefix("release:")
            matches = [
                item for item in held if f"{item[1]}" == name or item[1].split(":")[0] == name
            ]
            if not matches:
                return False
            held.remove(matches[-1])
            continue
        name, _, key = step.partition(":")
        if name not in ranks:
            return False
        rank = ranks[name]
        if held:
            top_rank, top = held[-1]
            if rank < top_rank:
                return False
            if rank == top_rank and (
                name not in multiple or not key or key <= top.partition(":")[2]
            ):
                return False
        held.append((rank, step))
    return True


def test_lock_sequences_follow_the_frozen_order() -> None:
    machines = _load("state-machines.json")
    hierarchy = machines["locks"]["hierarchy"]
    assert [lock["rank"] for lock in hierarchy] == sorted({lock["rank"] for lock in hierarchy})
    for sequence in machines["locks"]["sequences"]:
        assert _lock_sequence_valid(hierarchy, sequence["steps"]) is sequence["valid"], sequence[
            "id"
        ]


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
        } - {"nothing_to_recover", "sweep_restarts", "maintenance_rerun"}
        if recoveries:
            assert machine["name"] in crashing, machine["name"]


# ----------------------------------------------------------------------------
# Exhaustive interleaving of acquisition, reclamation, and purge

_CONTENDED_SIDE_LOCKS = frozenset({"maintenance_shared", "maintenance_exclusive"})


def _condition(atom: str, shared: dict[str, Any]) -> bool:
    return {
        "store_absent": shared["store"] == "absent",
        "store_present": shared["store"] == "present",
        "alias_absent": shared["alias"] is None,
        "alias_is_store": shared["alias"] == "K",
    }[atom]


def _explore(document: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    """Breadth-first search over every interleaving of the model's processes.

    A global state is the shared records, every lock holder, and each process's
    program counter, machine state, and held locks. Returns the violations found,
    the events executed, and the number of states visited.
    """
    hierarchy = {lock["name"]: lock for lock in document["locks"]["hierarchy"]}
    machines = {machine["name"]: machine for machine in document["machines"]}
    interleaving = document["interleaving"]
    programs = [interleaving["programs"][name] for name in model["processes"]]
    labels = [{step["label"]: step for step in program["steps"]} for program in programs]

    def freeze(shared: dict[str, Any], locks: dict[str, Any], procs: list[Any]) -> Any:
        return (
            tuple(sorted(shared.items())),
            tuple(sorted((key, value) for key, value in locks.items())),
            tuple(procs),
        )

    initial_shared = dict(interleaving["initial"])
    initial_procs = [
        (program["steps"][0]["label"], program["start"], frozenset()) for program in programs
    ]
    start: tuple[dict[str, Any], dict[str, Any], list[Any]] = (
        initial_shared,
        {"exclusive": None, "shared": frozenset()},
        initial_procs,
    )
    seen = {freeze(*start)}
    queue = deque([start])
    violations: set[str] = set()
    events: set[str] = set()

    def lock_name(item: dict[str, Any]) -> str:
        if item["lock"] == "maintenance":
            return f"maintenance_{item['mode']}"
        return f"{item['lock']}:{item['key']}"

    while queue:
        shared, locks, procs = queue.popleft()
        if shared["alias"] == "K" and shared["store"] != "present":
            violations.add("alias_names_absent_store")
        enabled = False
        live = False
        for index, (label, state, held) in enumerate(procs):
            if label == "end":
                continue
            live = True
            program = programs[index]
            step = labels[index][label]
            new_locks = {"exclusive": locks["exclusive"], "shared": locks["shared"]}
            new_held = set(held)
            blocked = False
            busy = False
            for item in step["acquire"]:
                name = lock_name(item)
                hierarchy_held = [h for h in new_held if h.split(":")[0] in hierarchy]
                if item["lock"] == "maintenance":
                    if item.get("wait") and hierarchy_held:
                        violations.add("blocking_side_lock_under_hierarchy_lock")
                    if item["mode"] == "exclusive" and item.get("wait"):
                        violations.add("exclusive_maintenance_blocks")
                    if item["mode"] == "shared":
                        available = new_locks["exclusive"] is None
                    else:
                        available = new_locks["exclusive"] is None and not new_locks["shared"]
                    if not available:
                        if item.get("wait"):
                            blocked = True
                        else:
                            busy = True
                        break
                    if item["mode"] == "shared":
                        new_locks["shared"] = new_locks["shared"] | {index}
                    else:
                        new_locks["exclusive"] = index
                    new_held.add(name)
                    continue
                rank = hierarchy[item["lock"]]["rank"]
                for other in hierarchy_held:
                    other_lock, _, other_key = other.partition(":")
                    other_rank = hierarchy[other_lock]["rank"]
                    ordered = other_rank < rank or (
                        other_rank == rank
                        and hierarchy[item["lock"]]["multiple"]
                        and other_key < item["key"]
                    )
                    if not ordered:
                        violations.add("hierarchy_order")
                if locks.get(name) is not None and locks.get(name) != index:
                    blocked = True
                    break
                new_locks[name] = index
                new_held.add(name)
            if blocked:
                continue
            enabled = True
            branch: dict[str, Any]
            if busy:
                branch = {
                    "event": step["busy"]["event"],
                    "effects": {},
                    "release": [],
                    "next": step["busy"]["next"],
                }
                new_locks = {"exclusive": locks["exclusive"], "shared": locks["shared"]}
                new_locks.update({k: v for k, v in locks.items() if ":" in k})
                new_held = set(held)
            else:
                new_locks.update(
                    {k: v for k, v in locks.items() if ":" in k and k not in new_locks}
                )
                candidates = [
                    b for b in step["branches"] if all(_condition(a, shared) for a in b["when"])
                ]
                if not candidates:
                    violations.add(f"no_branch:{label}")
                    continue
                branch = candidates[0]
            events.add(branch["event"])
            next_state = state
            if program["machine"] is not None:
                machine = machines[program["machine"]]
                matches = [
                    t
                    for t in machine["transitions"]
                    if t["from"] == state and t["event"] == branch["event"]
                ]
                if len(matches) != 1:
                    violations.add(f"unknown_transition:{state}:{branch['event']}")
                    continue
                transition = matches[0]
                contended = {
                    lock
                    for lock in transition["holds"]
                    if lock in hierarchy or lock in _CONTENDED_SIDE_LOCKS
                }
                held_names = {h.split(":")[0] for h in new_held}
                if contended != held_names:
                    violations.add(f"holds_mismatch:{branch['event']}")
                next_state = transition["to"]
            new_shared = dict(shared)
            new_shared.update(branch["effects"])
            releases = branch["release"]
            if "all" in releases:
                releases = sorted({h.split(":")[0] for h in new_held})
            for release in releases:
                for name in [h for h in new_held if h.split(":")[0] == release]:
                    new_held.discard(name)
                    if name == "maintenance_shared":
                        new_locks["shared"] = new_locks["shared"] - {index}
                    elif name == "maintenance_exclusive":
                        new_locks["exclusive"] = None
                    else:
                        new_locks[name] = None
            if branch["next"] == "end" and new_held:
                violations.add(f"locks_held_at_end:{branch['event']}")
            new_procs = list(procs)
            new_procs[index] = (branch["next"], next_state, frozenset(new_held))
            clean_locks = {
                k: v for k, v in new_locks.items() if v is not None or k in ("exclusive", "shared")
            }
            successor = (new_shared, clean_locks, new_procs)
            key = freeze(*successor)
            if key not in seen:
                seen.add(key)
                queue.append(successor)
        if live and not enabled:
            violations.add("deadlock")
    return {"violations": violations, "events": events, "states": len(seen)}


def test_interleavings_never_strand_an_alias_or_violate_lock_order() -> None:
    document = _load("state-machines.json")
    for model in document["interleaving"]["models"]:
        result = _explore(document, model)
        if model["expect"] == "safe":
            assert result["violations"] == set(), (model["id"], result["violations"])
        else:
            assert model["expect"] in result["violations"], (model["id"], result["violations"])
        assert set(model["unreachable_events"]).isdisjoint(result["events"]), model["id"]
        assert set(model["reachable_events"]) <= result["events"], (
            model["id"],
            set(model["reachable_events"]) - result["events"],
        )
        assert result["states"] > 1, model["id"]
