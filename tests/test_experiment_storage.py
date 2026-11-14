"""An experiment's evidence lives where a restart cannot remove it.

The checks behind docs/development.md, "Durable Storage", for experiment records:

- no record points its evidence at a session scratchpad or an operating system temporary
  directory;
- every file a record names is in the repository: its protocol, with the sha256 the record
  cites, the sample files in `method.record`, and every relative link;
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

ROOT = Path(__file__).resolve().parents[1]
LOOP = ROOT / "explorations" / "performance-loop"
EXPERIMENTS = LOOP / "experiments"
SCHEMA = EXPERIMENTS / "experiment.schema.yaml"

# Anywhere in a record: an agent's scratchpad, which no one else can read either.
SCRATCHPAD = re.compile(r"scratchpad", re.IGNORECASE)
# Outside a fenced block: a temporary directory the system empties. A bare `/tmp` that says where
# something ran, not what was kept, is not a path into it. Inside one, a
# "Reproducing" recipe may write an intermediate there, because rerunning it recreates it.
TEMPORARY = re.compile(
    r"(?<![\w.~])/tmp/|/private/tmp|/var/folders|\$\{?TMPDIR\b|\bmktemp\b", re.IGNORECASE
)
FENCE = re.compile(r"^(`{3,}|~{3,})")
SHA256 = re.compile(r"\b[0-9a-f]{64}\b")
PREREGISTRATION = re.compile(r"pre-?registration", re.IGNORECASE)
LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")
NAMED_FILE = re.compile(r"\bexp-[\w.-]+\.(?:jsonl|json|mjs|py|txt)\b")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

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


def _protocol_schema() -> dict[str, Any]:
    schema = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))
    return schema["properties"]["method"]["properties"]["protocol"]


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
    protocol = method.get("protocol")
    if protocol is not None:
        jsonschema.validate(protocol, _protocol_schema())
        target = (EXPERIMENTS / str(protocol["path"])).resolve()
        assert target.parent == EXPERIMENTS, (
            f"{path.name}: protocol {protocol['path']} is not beside the record"
        )
        assert target.is_file(), f"{path.name}: protocol {target.name} is not committed"
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        assert digest == protocol["sha256"], (
            f"{path.name}: {target.name} hashes to {digest}, not the {protocol['sha256']} "
            "the record cites; a recorded round's protocol is not edited again"
        )
    record = method.get("record")
    if isinstance(record, str):
        for name in NAMED_FILE.findall(record):
            found = [EXPERIMENTS / name, LOOP / name, *EXPERIMENTS.rglob(name)]
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
    cites = bool(PREREGISTRATION.search(body) and SHA256.search(body))
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


def test_an_unclosed_fence_is_refused() -> None:
    with pytest.raises(AssertionError, match="never closed"):
        _transient_lines("```shell\n/tmp/x\n")
