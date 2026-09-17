"""Pin the repository-cache contracts frozen before the cache is implemented.

The fixtures under ``tests/fixtures/repository-cache/`` are the contract the
format-foundation and acquisition implementations consume: the root-argument URL grammar,
source and repository-store identity, slug derivation, Git version gates,
and the lock, publication, lease, trash, and quarantine state machines.

Rules with a production implementation replay the fixtures through it:
source and store identity, store keys, and slugs through
``metabrowser.cache.identity``, and the lock hierarchy, lock-file placement, and lock
sequences through ``metabrowser.cache.locks``. The sweep, trash, quarantine, and store
reclamation machines replay against ``metabrowser.cache.reclaim`` in
``tests/test_cache_reclaim.py``.

Rules whose implementation belongs to a later phase keep a small reference oracle
written from the fixture's own prose: the root-argument URL grammar (Phase 1B-a), the
Git version gates (Phase 1B-a), and object requests (the object-job port). Each oracle
proves its frozen rules are complete and consistent, and is replaced by the production
function when that lands; it is a specification aid, not a second implementation to
keep. The state-machine well-formedness checks and the exhaustive interleaving
exploration verify the design itself and stay.
"""

from __future__ import annotations

import json
import math
import re
import string
from collections import deque
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator

from metabrowser.cache import identity, locks
from metabrowser.cache.locks import HIERARCHY_RANKS, LockKind, LockOrder, LockOrderError
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
        classified = classify(record["input"], defaults)
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
                cast(identity.GitTransport, classify(value, defaults)["transport"]),
                classify(value, defaults)["normalized"],
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
    cap = cast(int, spec["request"]["rejected_leaf_cap"])
    sizes: list[int] = []
    accepted: list[str] = []
    rejected: list[str] = []
    deferred: list[str] = []

    def attempt(oids: list[str]) -> None:
        if len(rejected) >= cap:
            deferred.extend(oids)
            return
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
        return {
            "outcome": "job_failed",
            "accepted": [],
            "rejected": [],
            "deferred": [],
            "request_sizes": sizes,
        }
    outcome = "partial" if rejected or deferred else "complete"
    return {
        "outcome": outcome,
        "accepted": accepted,
        "rejected": rejected,
        "deferred": deferred,
        "request_sizes": sizes,
    }


def job_source_outcome(case: dict[str, Any]) -> str:
    """The frozen fetch-job source rule."""
    remotes = cast(dict[str, dict[str, bool]], case["store"]["remotes"])
    remote = remotes.get(case["job"]["remote"])
    if remote is None:
        return "not_a_recorded_remote"
    if case["store"]["partial"] and not remote["promisor"]:
        return "not_a_promisor_remote"
    _source, _, destination = cast(str, case["job"]["refspec"]).lstrip("+").partition(":")
    if not destination.startswith("refs/metabrowser/jobs/<job-id>/"):
        return "destination_not_job_private"
    return "accepted"


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
    cap = spec["request"]["rejected_leaf_cap"]
    for case in spec["request_cases"]:
        assert case["failure_class"] in classes, case["id"]
        result = split_request(
            spec, case["wants"], set(case["rejected_by_server"]), case["failure_class"]
        )
        assert result == case["expected"], case["id"]
        assert sorted(result["accepted"] + result["rejected"] + result["deferred"]) == (
            sorted(case["wants"]) if result["outcome"] != "job_failed" else []
        ), case["id"]
        assert len(result["rejected"]) <= cap, case["id"]
        rejected = len(case["rejected_by_server"]) if result["outcome"] != "job_failed" else 0
        depth = max(1, math.ceil(math.log2(max(len(case["wants"]), 1))))
        assert len(result["request_sizes"]) <= 1 + 2 * min(rejected, cap) * depth, case["id"]
    assert 1 + 2 * cap * math.ceil(math.log2(50_000)) == 257


def test_fetch_jobs_use_only_recorded_promisor_remotes() -> None:
    spec = _load("object-requests.json")["job_sources"]
    outcomes = {job_source_outcome(case) for case in spec["cases"]}
    assert outcomes == {
        "accepted",
        "not_a_recorded_remote",
        "not_a_promisor_remote",
        "destination_not_job_private",
    }
    for case in spec["cases"]:
        assert job_source_outcome(case) == case["expected"], case["id"]


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
        "trash_entry": (lambda: locks.trash_entry_lock(home, "e1"), {"<entry>": "e1"}),
        "job_entry": (lambda: locks.job_entry_lock(home, "j1"), {"<job-id>": "j1"}),
        "maintenance_shared": (lambda: locks.store_lease(home, store), {"<store-key>": store}),
        "maintenance_exclusive": (
            lambda: locks.store_maintenance_lock(home, store),
            {"<store-key>": store},
        ),
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

    initial_shared = dict(model.get("initial", interleaving["initial"]))
    crashes = {(crash["program"], crash["before"]): crash for crash in model.get("crashes", [])}
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
            if label in ("end", "crashed"):
                continue
            live = True
            program = programs[index]
            crash = crashes.get((model["processes"][index], label))
            if crash is not None:
                events.add(f"crash:{model['processes'][index]}:{label}")
                if program["machine"] is not None:
                    machine_states = {
                        entry["name"]: entry for entry in machines[program["machine"]]["states"]
                    }
                    if machine_states[state].get("on_crash") != crash["recovery"]:
                        violations.add(f"crash_recovery_mismatch:{state}")
                crashed_locks = {"exclusive": locks["exclusive"], "shared": locks["shared"]}
                crashed_locks.update({k: v for k, v in locks.items() if ":" in k})
                for name in held:
                    if name == "maintenance_shared":
                        crashed_locks["shared"] = crashed_locks["shared"] - {index}
                    elif name == "maintenance_exclusive":
                        crashed_locks["exclusive"] = None
                    else:
                        crashed_locks[name] = None
                crashed_procs = list(procs)
                crashed_procs[index] = ("crashed", state, frozenset())
                crashed = (
                    dict(shared),
                    {
                        k: v
                        for k, v in crashed_locks.items()
                        if v is not None or k in ("exclusive", "shared")
                    },
                    crashed_procs,
                )
                crashed_key = freeze(*crashed)
                if crashed_key not in seen:
                    seen.add(crashed_key)
                    queue.append(crashed)
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
