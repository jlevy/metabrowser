"""An experiment's evidence lives where a restart cannot remove it.

The checks behind explorations/performance-loop/README.md, "Durable Storage", for
experiment records:

- no record points its evidence at a session scratchpad, or, outside a fenced recipe, at an
  operating system temporary directory;
- every file a record names is in the repository: its protocol and registered analysis
  scripts, with the sha256 `method.protocol` and `method.analysis` give, the files
  `method.record` names, and every relative link;
- each analysis script's hash is one the protocol registered, or the record declares the
  change as a deviation, gives the registered hash, and rules on it under a heading;
- a record that cites a pre-registration by sha256, or is dated from the rule on, names its
  committed protocol in `method.protocol`.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import jsonschema
import pytest
import yaml
from softschema import Contract, validate_artifact

ROOT = Path(__file__).resolve().parents[1]
LOOP = ROOT / "explorations" / "performance-loop"
EXPERIMENTS = LOOP / "experiments"
SCHEMA = EXPERIMENTS / "experiment.schema.yaml"

# Anywhere in a record: an agent's scratchpad, which no one else can read either.
SCRATCHPAD = re.compile(r"scratchpad", re.IGNORECASE)
# Outside a fenced block: a temporary directory the system empties. Inside one, a
# "Reproducing" recipe may write an intermediate there, because rerunning it recreates it.
# A bare `/tmp` that says where something ran, not what was kept, is not a path into it.
TEMPORARY = re.compile(
    r"(?<![\w.~])/tmp/|/private/tmp|/var/folders|\$\{?TMPDIR\b|\bmktemp\b", re.IGNORECASE
)
FENCE = re.compile(r"^(`{3,}|~{3,})")
SHA256 = re.compile(r"\b[0-9a-f]{64}\b", re.IGNORECASE)
PREREGISTRATION = re.compile(r"pre[- ]?registration|protocol file", re.IGNORECASE)
LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")
NAMED_FILE = re.compile(r"(?<![\w./-])[\w./-]*[\w-]\.(?:jsonl|json|mjs|py|txt)\b")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DEVIATION_HEADING = re.compile(r"^#{1,6}\s.*\bDeviation", re.IGNORECASE)

# Records written before the rule that point at evidence that no longer exists, with why.
# The record is corrected, not rewritten, so its text stays; nothing new joins this list.
KNOWN_LOST: dict[str, str] = {
    "exp-040": "its scripts, raw JSONL, and server logs were kept in a session scratchpad",
}

# The first day every record must name its committed protocol: the day after this rule
# merged. Set it to the merge date's next day if the merge moves.
PROTOCOL_REQUIRED_FROM = "2026-11-15"


def _records() -> list[Path]:
    return sorted(EXPERIMENTS.glob("exp-*.md"))


def _split(path: Path) -> tuple[dict[str, Any], str]:
    """The record's `experiment` front matter and its body, split on whole `---` lines."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        return {}, "\n".join(lines)
    end = lines.index("---", 1)
    loaded = yaml.safe_load("\n".join(lines[1:end])) or {}
    experiment = loaded.get("experiment") if isinstance(loaded, dict) else None
    return (experiment if isinstance(experiment, dict) else {}), "\n".join(lines[end + 1 :])


def _id(path: Path) -> str:
    match = re.match(r"(exp-\d{3})", path.name)
    return match.group(1) if match else path.stem


def _outside_fences(text: str) -> list[tuple[int, str, bool]]:
    """Each line as (number, text, fenced). A fence closes only on its own marker."""
    out: list[tuple[int, str, bool]] = []
    opener: str | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        marker = FENCE.match(line.strip())
        if marker and opener is None:
            opener = marker.group(1)
            continue
        closing = marker.group(1) if marker else None
        if closing and opener and closing.startswith(opener) and line.strip() == closing:
            opener = None
            continue
        out.append((number, line, opener is not None))
    assert opener is None, f"a {opener} fence is never closed"
    return out


def _transient_lines(text: str) -> list[str]:
    return [
        f"{number}: {line.strip()[:120]}"
        for number, line, fenced in _outside_fences(text)
        if SCRATCHPAD.search(line) or (not fenced and TEMPORARY.search(line))
    ]


def _method_schema(field: str) -> dict[str, Any]:
    schema = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))
    return schema["properties"]["method"]["properties"][field]


def _check_committed(name: str, field: str, entry: dict[str, Any]) -> Path:
    """A `{path, sha256}` entry names a file under experiments/, committed with that hash."""
    raw = Path(str(entry["path"]))
    target = (EXPERIMENTS / raw).resolve()
    assert ".." not in raw.parts and target.is_relative_to(EXPERIMENTS), (
        f"{name}: {field} {entry['path']} is not under experiments/"
    )
    assert target.is_file(), f"{name}: {field} {entry['path']} is not committed"
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    assert digest == entry["sha256"], (
        f"{name}: {field} {entry['path']} hashes to {digest}, not the {entry['sha256']} the "
        "record cites"
    )
    return target


def _has_deviation_heading(body: str) -> bool:
    return any(
        not fenced and DEVIATION_HEADING.match(line) for _, line, fenced in _outside_fences(body)
    )


def _check_method_files(name: str, method: dict[str, Any], body: str) -> None:
    """The committed protocol and registered analysis scripts a record's method names.

    The protocol is beside the record and keeps its hash. Each analysis script is under
    experiments/ and matches the hash its entry cites; the hash the protocol registered
    is that one, or, for a script changed after registration, the entry's
    `registered_sha256`, and the record then has a "Deviation" heading.
    """
    protocol = method.get("protocol")
    registered: set[str] = set()
    if protocol is not None:
        jsonschema.validate(protocol, _method_schema("protocol"))
        target = _check_committed(name, "method.protocol", protocol)
        assert target.parent == EXPERIMENTS, (
            f"{name}: method.protocol {protocol['path']} is not beside the record; "
            "a recorded round's protocol is not edited again"
        )
        registered = {h.lower() for h in SHA256.findall(target.read_text(encoding="utf-8"))}
    analysis = method.get("analysis")
    if analysis is None:
        return
    jsonschema.validate(analysis, _method_schema("analysis"))
    assert protocol is not None, f"{name}: method.analysis needs the method.protocol it registers"
    for entry in analysis:
        _check_committed(name, "method.analysis", entry)
        cited = entry.get("registered_sha256", entry["sha256"])
        assert cited in registered, (
            f"{name}: method.analysis {entry['path']} cites {cited}, which "
            f"{protocol['path']} does not register; a script changed after registration "
            "gives the protocol's hash as registered_sha256 and a deviation"
        )
        if "registered_sha256" in entry:
            assert entry["registered_sha256"] != entry["sha256"], (
                f"{name}: method.analysis {entry['path']} declares a deviation but is unchanged"
            )
            assert _has_deviation_heading(body), (
                f"{name}: method.analysis {entry['path']} declares a deviation, and the record "
                'has no heading containing "Deviation" that rules on it'
            )


@pytest.mark.parametrize("path", _records(), ids=_id)
def test_a_record_has_front_matter_and_an_iso_date(path: Path) -> None:
    front, _ = _split(path)
    assert front, f"{path.name} has no `experiment` front matter"
    assert DATE.match(str(front.get("date", ""))), (
        f"{path.name}: date {front.get('date')!r} is not YYYY-MM-DD"
    )


def test_no_record_points_its_evidence_at_a_transient_location() -> None:
    offenders: dict[str, list[str]] = {}
    for path in _records():
        if _id(path) in KNOWN_LOST:
            continue
        lines = _transient_lines(path.read_text(encoding="utf-8"))
        if lines:
            offenders[path.name] = lines
    assert not offenders, (
        "a record points its evidence at a scratchpad or temporary directory, which a "
        f"restart empties; commit it beside the record or keep it in attic/: {offenders}"
    )


def test_known_lost_records_exist_and_are_dated_before_the_rule() -> None:
    by_id = {_id(path): path for path in _records()}
    for experiment_id in KNOWN_LOST:
        assert experiment_id in by_id, f"{experiment_id} is not a record any more"
        date = str(_split(by_id[experiment_id])[0].get("date", ""))
        assert date < PROTOCOL_REQUIRED_FROM, f"{experiment_id} is dated after the rule"


@pytest.mark.parametrize("path", _records(), ids=_id)
def test_every_file_a_record_names_is_in_the_repository(path: Path) -> None:
    front, body = _split(path)
    method = front.get("method") or {}
    _check_method_files(path.name, method, body)
    record = method.get("record")
    if isinstance(record, str):
        for name in NAMED_FILE.findall(record):
            found = [EXPERIMENTS / name, LOOP / name, ROOT / name, *LOOP.rglob(Path(name).name)]
            assert any(candidate.is_file() for candidate in found), (
                f"{path.name}: method.record names {name}, which is not committed"
            )
    for number, line, fenced in _outside_fences(body):
        if fenced:
            continue
        for link in LINK.findall(line):
            if re.match(r"^[a-z][a-z0-9+.-]*:", link):
                continue
            target = (path.parent / unquote(link)).resolve()
            assert target.is_relative_to(ROOT), f"{path.name}:{number}: {link} leaves the repo"
            assert target.exists(), f"{path.name}:{number}: {link} is not in the repository"


@pytest.mark.parametrize("path", _records(), ids=_id)
def test_a_record_that_cites_a_protocol_names_it(path: Path) -> None:
    front, body = _split(path)
    method = front.get("method") or {}
    if method.get("protocol") or _id(path) in KNOWN_LOST:
        return
    paragraphs = re.split(r"\n\s*\n", body)
    cites = any(PREREGISTRATION.search(p) and SHA256.search(p) for p in paragraphs)
    assert not cites, (
        f"{path.name} cites a pre-registration by sha256 but names no committed protocol "
        "in method.protocol"
    )
    assert str(front.get("date", "")) < PROTOCOL_REQUIRED_FROM, (
        f"{path.name} is dated {front.get('date')} and names no committed protocol in "
        "method.protocol"
    )


def test_the_transient_check_sees_what_it_must() -> None:
    sample = "\n".join(
        [
            "Logs are in the session scratchpad.",
            "Kept at /private/tmp/claude/run.",
            "Output went to /tmp/out.jsonl.",
            "Written under $TMPDIR and ${TMPDIR}/x.",
            "Raw files sat in /var/folders/ab/T/.",
            "The env dir came from mktemp -d.",
            "Kept in ~/tmp/runs and backup/tmp/x, which a restart keeps.",
            "````markdown",
            "```shell",
            "a nested fence line is not a close",
            "```",
            "node filter.mjs --out /tmp/judged.jsonl",
            "````",
            "~~~",
            "cp x /tmp/y",
            "~~~",
        ]
    )
    flagged = [line.split(":", 1)[0] for line in _transient_lines(sample)]
    assert flagged == ["1", "2", "3", "4", "5", "6"]


def _sha256(name: str) -> str:
    return hashlib.sha256((EXPERIMENTS / name).read_bytes()).hexdigest()


def test_the_analysis_check_refuses_what_it_must() -> None:
    # exp-079's protocol registers exclude.mjs and the subdirectory derive script as
    # committed, and analyze.mjs as b09ab7c8..., which the committed file no longer is.
    protocol = {"path": "exp-079-protocol.txt", "sha256": _sha256("exp-079-protocol.txt")}
    exclude = {"path": "exp-079-exclude.mjs", "sha256": _sha256("exp-079-exclude.mjs")}
    nested = "exp-065-instruments/derive-h92-h106.mjs"
    derive = {"path": nested, "sha256": _sha256(nested)}
    analyze = {"path": "exp-079-analyze.mjs", "sha256": _sha256("exp-079-analyze.mjs")}
    registered = "b09ab7c8dd47d67fe28df1f30e1b543e5d26e095584f615158a36ccf293b76d6"
    deviated = {**analyze, "registered_sha256": registered, "deviation": "edited after reading"}
    ruled = "## Deviation from the Protocol\n\nThe analysis changed.\n"

    def check(analysis: object, body: str = "") -> None:
        _check_method_files("synthetic", {"protocol": protocol, "analysis": analysis}, body)

    check([exclude, derive])
    check([deviated], ruled)
    refused: dict[str, tuple[list[dict[str, str]], str]] = {
        "does not register": ([analyze], ruled),
        "hashes to": ([{**exclude, "sha256": analyze["sha256"]}], ""),
        "is not committed": ([{**exclude, "path": "exp-999-analyze.mjs"}], ""),
        "is not under": ([{**exclude, "path": "../README.md"}], ""),
        "not under": ([{**exclude, "path": "exp-065-instruments/../exp-079-exclude.mjs"}], ""),
        "no heading": ([deviated], "The analysis changed.\n```\n## Deviation\n```\n"),
        "is unchanged": (
            [{**exclude, "registered_sha256": exclude["sha256"], "deviation": "x"}],
            "",
        ),
    }
    refused_unregistered = {**deviated, "registered_sha256": "0" * 64}
    for message, (analysis, body) in refused.items():
        with pytest.raises(AssertionError, match=message):
            check(analysis, body)
    with pytest.raises(AssertionError, match="does not register"):
        check([refused_unregistered], ruled)
    with pytest.raises(AssertionError, match="needs the method.protocol"):
        _check_method_files("synthetic", {"analysis": [exclude]}, "")
    for malformed in (
        [],
        exclude,
        [{"path": exclude["path"]}],
        [{**analyze, "registered_sha256": registered}],
        [{**analyze, "deviation": "edited"}],
    ):
        with pytest.raises(jsonschema.ValidationError):
            check(malformed, ruled)


def test_an_unclosed_fence_is_refused() -> None:
    with pytest.raises(AssertionError, match="never closed"):
        _transient_lines("```shell\n/tmp/x\n")


def test_annotated_or_diagnostic_records_match_the_contract() -> None:
    contract = Contract(
        id="metabrowser.loadtime:Experiment/v1",
        envelope_key="experiment",
        schema_path=SCHEMA,
    )
    for path in _records():
        front, _ = _split(path)
        if "observations" in front or "annotations" in front:
            result = validate_artifact(path, contract=contract, require=("structural",))
            assert result.structural.execution == "completed", path.name
            assert result.ok, result.structural.errors
