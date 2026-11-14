"""An experiment's evidence lives where a restart cannot remove it.

The operating system empties `/tmp`, `/private/tmp`, `$TMPDIR`, and `/var/folders` on
restart, and an agent's session scratchpad lives under `/private/tmp`. On 2026-11-14 one
restart took a campaign's series lock and the protocol files that committed records cite by
sha256 (docs/development.md, "Durable Storage"). These checks keep a record's evidence in
the repository: no record points its evidence at a transient location, every file a record
names is committed, and a record from after the rule names its committed protocol.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
LOOP = ROOT / "explorations" / "performance-loop"
EXPERIMENTS = LOOP / "experiments"

# Anywhere in a record: an agent's scratchpad or a temporary directory the system empties.
TRANSIENT = re.compile(r"scratchpad|/private/tmp|/var/folders|\$TMPDIR", re.IGNORECASE)
# Outside a fenced block: `/tmp/`. Inside one, a "Reproducing" recipe may write an
# intermediate there, because rerunning the recipe recreates it.
TMP = re.compile(r"(?<![\w.])/tmp/")
FENCE = re.compile(r"^(`{3,}|~{3,})")

# Records written before the rule that point at evidence that no longer exists, with why.
# The record is corrected, not rewritten, so its text stays; nothing new joins this list.
KNOWN_LOST: dict[str, str] = {
    "exp-040": "its scripts, raw JSONL, and server logs were kept in a session scratchpad",
}

# The first day a record must name its committed protocol: the day after the rule landed.
PROTOCOL_REQUIRED_FROM = "2026-11-15"


def _records() -> list[Path]:
    return sorted(EXPERIMENTS.glob("exp-*.md"))


def _front(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    loaded = yaml.safe_load(text.split("---", 2)[1]) or {}
    experiment = loaded.get("experiment") if isinstance(loaded, dict) else None
    return experiment if isinstance(experiment, dict) else {}


def _id(path: Path) -> str:
    match = re.match(r"(exp-\d{3})", path.name)
    return match.group(1) if match else path.stem


def _transient_lines(text: str) -> list[str]:
    found: list[str] = []
    fenced = False
    for number, line in enumerate(text.splitlines(), start=1):
        if FENCE.match(line.strip()):
            fenced = not fenced
            continue
        if TRANSIENT.search(line) or (not fenced and TMP.search(line)):
            found.append(f"{number}: {line.strip()[:120]}")
    return found


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
        date = str(_front(by_id[experiment_id]).get("date", ""))
        assert date < PROTOCOL_REQUIRED_FROM, f"{experiment_id} is dated after the rule"


@pytest.mark.parametrize("path", _records(), ids=lambda path: _id(path))
def test_every_file_a_record_names_is_committed(path: Path) -> None:
    method = _front(path).get("method") or {}
    protocol = method.get("protocol")
    if protocol is not None:
        target = EXPERIMENTS / str(protocol["path"])
        assert target.is_file(), f"{path.name}: protocol {target.name} is not committed"
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        assert digest == protocol["sha256"], (
            f"{path.name}: {target.name} hashes to {digest}, not the {protocol['sha256']} "
            "the record cites; a recorded round's protocol is not edited again"
        )
    record = method.get("record")
    if isinstance(record, str) and record.endswith((".jsonl", ".json")):
        candidates = [EXPERIMENTS / record, LOOP / record, ROOT / record]
        assert any(candidate.is_file() for candidate in candidates), (
            f"{path.name}: its samples {record} are not committed"
        )


@pytest.mark.parametrize("path", _records(), ids=lambda path: _id(path))
def test_a_record_from_after_the_rule_names_its_protocol(path: Path) -> None:
    front = _front(path)
    if str(front.get("date", "")) < PROTOCOL_REQUIRED_FROM:
        return
    method = front.get("method") or {}
    assert method.get("protocol"), (
        f"{path.name} is dated {front.get('date')} and names no committed protocol in "
        "method.protocol"
    )


def test_the_transient_check_sees_what_it_must() -> None:
    sample = "\n".join(
        [
            "Logs are in the session scratchpad.",
            "Kept at /private/tmp/claude/run.",
            "Output went to /tmp/out.jsonl.",
            "```shell",
            "node filter.mjs --out /tmp/judged.jsonl",
            "```",
        ]
    )
    flagged = _transient_lines(sample)
    assert [line.split(":", 1)[0] for line in flagged] == ["1", "2", "3"]
