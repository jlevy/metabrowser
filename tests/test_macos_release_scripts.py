"""The macOS app's release scripts, checked where Apple's tools are not.

`apps/macos/scripts/test-release-logic.sh` runs what the release scripts decide on
stand-ins for Apple's tools: the arguments codesign and notarytool get, the notary log
reader, `notarize.sh` end to end, and the signing doctor's checks on generated
certificates. It needs bash, jq, openssl, and shasum, and nothing from Xcode, so `make
test` runs it here, and Linux CI with it; `make macos-test` runs it on a Mac too, with
macOS's bash and LibreSSL.

The pin below holds the one copy a document makes of those scripts' values: the
SHA-256 of the committed G2 intermediate, which `SUPPLY-CHAIN-SECURITY.md` records as
reviewed and `apps/macos/scripts/signing-lib.sh` checks.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
APP = REPO_ROOT / "apps/macos"
LOGIC_TESTS = APP / "scripts/test-release-logic.sh"
SIGNING_LIB = APP / "scripts/signing-lib.sh"
SUPPLY_CHAIN = REPO_ROOT / "SUPPLY-CHAIN-SECURITY.md"

# The script makes a handful of RSA keys and runs notarize.sh six times; it takes a few
# seconds, so this bounds a hang, not the work.
LOGIC_TIMEOUT_S = 300


def _shell_value(name: str) -> str:
    match = re.search(rf"^{name}=(\S+)$", SIGNING_LIB.read_text(), re.MULTILINE)
    assert match, f"{SIGNING_LIB.relative_to(REPO_ROOT)} no longer sets {name}"
    return match.group(1)


def test_release_logic_runs_without_apples_tools() -> None:
    missing = [tool for tool in ("bash", "jq", "openssl", "shasum") if shutil.which(tool) is None]
    if missing:
        pytest.skip(f"the release-logic checks need {', '.join(missing)} on PATH")
    result = subprocess.run(
        ["bash", str(LOGIC_TESTS)],
        capture_output=True,
        text=True,
        timeout=LOGIC_TIMEOUT_S,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Release-logic checks passed" in result.stdout


def test_the_committed_intermediate_is_the_reviewed_one() -> None:
    reviewed = _shell_value("g2_intermediate_sha256")
    certificate = APP / _shell_value("g2_intermediate")
    assert hashlib.sha256(certificate.read_bytes()).hexdigest() == reviewed
    assert f"`{reviewed}`" in SUPPLY_CHAIN.read_text(), (
        "SUPPLY-CHAIN-SECURITY.md must record the SHA-256 that signing-lib.sh checks"
    )
