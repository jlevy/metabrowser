"""Reject private workspace residue before MetaBrowser is published."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".git", ".venv", "dist", "node_modules", "__pycache__"}
SKIP_ROOTS = (ROOT / ".tbd" / "docs",)
BANNED_TOKEN_HASHES: dict[str, str] = {
    "31523fdddcd5294e2bc6cc775fba79e2597e6d45bc0a995c548493038ebea33f": "private name",
    "431c8f4eb977db1139192b703a0dbb36e9e3d89352c6983851ead2faf62a40a8": "private name",
    "2d53000528ed0be7f64e8498c577123bb9bbbb560223db2e0f70dd690e2b1aa1": "private name",
    "b526066864bb66f02f74b77aca24fa328c325c6f6d71f6efbf9957b874490b55": "private name",
    "e498282813b5fd5e888a0b7ea0a2da392447b2f9bb3a3f8cecbec00c27a0f1b9": "private name",
    "5b07a3b9cb35d98a05f18953b21f9768408adfd1816adc85ed70105fc826bb22": "private name",
    "a833bf726937b154114a299f100ee4eaa7f12ade82b1901f9d98c721df8bf5e4": "private name",
    "7db84657b37ddf61debdabcc7a71405574ff0daf5aa2e1775241c5bb07d407d3": "private name",
    "772f69d755ecccbba56351e6c3b53ef408e75ccdcac2dbf6adc5f5a291e7b498": "private name",
    "31aafbde8c01354c3f87bfe48a275df10d4007749369b35b139ac9da01e4f80f": "private name",
    "40fc2a07d586bb898773ec9ed4c696889e5530d33aa1109db97f4af07f7f3d2d": "private name",
    "6ec084924a26e0b8d74aed80306fd4212cd96dbe1be6371ad8d48652c27b732a": "private name",
}
TOKEN_PATTERN = re.compile(r"[a-z][a-z0-9_-]*", re.IGNORECASE)
ISSUE_ID_PATTERN = re.compile(r"\b([a-z][a-z0-9]{1,15})-[a-z0-9]{4,}\b", re.IGNORECASE)
PRIVATE_ISSUE_PREFIX_HASHES = frozenset(
    {"0035e3bed3a10ebe81bc85bbf80cc092871ba344926efa491f195e36cc7e003b"}
)
BANNED_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private plan path", re.compile(r"\bdocs/project/|\bplan-20\d{2}-", re.IGNORECASE)),
    ("private pull-request reference", re.compile(r"\bPR[- ]?#?\d+\b", re.IGNORECASE)),
    ("private home path", re.compile(r"/(?:Users|home)/[^/\s]+/")),
)


def _text_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if path == Path(__file__).resolve():
            continue
        if any(path.is_relative_to(skip_root) for skip_root in SKIP_ROOTS):
            continue
        if not path.is_file() or any(part in SKIP_PARTS for part in path.parts):
            continue
        try:
            path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        files.append(path)
    return files


def find_hygiene_findings(source: str, text: str) -> list[str]:
    """Return public-hygiene findings for a path or archive member."""
    findings: list[str] = []
    combined = f"{source}\n{text}"
    for match in TOKEN_PATTERN.finditer(combined):
        digest = hashlib.sha256(match.group(0).lower().encode()).hexdigest()
        label = BANNED_TOKEN_HASHES.get(digest)
        if label is not None:
            line = text.count("\n", 0, max(0, match.start() - len(source) - 1)) + 1
            findings.append(f"{source}:{line}: {label}")
    for match in ISSUE_ID_PATTERN.finditer(combined):
        prefix_digest = hashlib.sha256(match.group(1).lower().encode()).hexdigest()
        if prefix_digest in PRIVATE_ISSUE_PREFIX_HASHES:
            line = text.count("\n", 0, max(0, match.start() - len(source) - 1)) + 1
            findings.append(f"{source}:{line}: copied issue identifier")
    for label, pattern in BANNED_PATTERNS:
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            findings.append(f"{source}:{line}: {label}")
    return findings


def main() -> int:
    findings: list[str] = []
    for path in _text_files():
        relative = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")
        findings.extend(find_hygiene_findings(str(relative), text))
    if findings:
        print("Public hygiene check failed:")
        print("\n".join(f"- {finding}" for finding in findings))
        return 1
    print("Public hygiene checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
