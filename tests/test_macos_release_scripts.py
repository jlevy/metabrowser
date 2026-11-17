"""The macOS app's release scripts, checked where Apple's tools are not.

`apps/macos/scripts/test-release-logic.sh` runs what the release scripts decide on
stand-ins for Apple's tools: the arguments codesign and notarytool get, the notary log
reader, `notarize.sh` end to end, and the signing doctor's checks on generated
certificates. It needs bash, jq, openssl, pgrep, and shasum, and nothing from Xcode, so
`make test` runs it here, and Linux CI with it; `make macos-test` runs it on a Mac too,
with macOS's bash and LibreSSL. Without one of those tools the script stops and names
it, and the test fails: a skip would drop the only Linux coverage of these scripts.

The pins below hold the copies documents make of the scripts' values: the SHA-256 of
the committed G2 intermediate, which `apps/macos/scripts/signing-lib.sh` checks, and of
the Apple Root CA fixture, which the logic tests check before they verify the
intermediate's chain against it, both of which `SUPPLY-CHAIN-SECURITY.md` records; and
the release keychain's idle lock, which the runbook in `apps/macos/README.md` gives in
the owner's command.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
APP = REPO_ROOT / "apps/macos"
LOGIC_TESTS = APP / "scripts/test-release-logic.sh"
SIGNING_LIB = APP / "scripts/signing-lib.sh"
ROOT_FIXTURE = APP / "scripts/fixtures/AppleIncRootCertificate.cer"
SUPPLY_CHAIN = REPO_ROOT / "SUPPLY-CHAIN-SECURITY.md"
RUNBOOK = APP / "README.md"

# The script makes eight RSA keys, runs notarize.sh about ten times and the doctor about
# forty, each a few dozen processes: 18 s on a loaded 4-CPU Linux container (2026-11-17),
# so the test raises its budget past the suite's 60 s, and the inner bound sits below it
# to stop a hang with the script's output.
LOGIC_TIMEOUT_S = 100
LOGIC_BUDGET_S = 120


def _shell_value(script: Path, name: str) -> str:
    match = re.search(rf"^{name}=(\S+)$", script.read_text(), re.MULTILINE)
    assert match, f"{script.relative_to(REPO_ROOT)} no longer sets {name}"
    return match.group(1)


@pytest.mark.timeout(LOGIC_BUDGET_S)
def test_release_logic_runs_without_apples_tools() -> None:
    result = subprocess.run(
        ["bash", str(LOGIC_TESTS)],
        capture_output=True,
        text=True,
        timeout=LOGIC_TIMEOUT_S,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Release-logic checks passed" in result.stdout


@pytest.mark.parametrize(
    ("script", "name", "file_name", "certificate"),
    [
        (SIGNING_LIB, "g2_intermediate_sha256", "g2_intermediate", None),
        (LOGIC_TESTS, "apple_root_ca_sha256", None, ROOT_FIXTURE),
    ],
    ids=["g2-intermediate", "apple-root-ca"],
)
def test_the_committed_certificates_are_the_reviewed_ones(
    script: Path, name: str, file_name: str | None, certificate: Path | None
) -> None:
    reviewed = _shell_value(script, name)
    path = APP / _shell_value(script, file_name) if file_name else certificate
    assert path is not None
    assert hashlib.sha256(path.read_bytes()).hexdigest() == reviewed
    assert f"`{reviewed}`" in SUPPLY_CHAIN.read_text(), (
        f"SUPPLY-CHAIN-SECURITY.md must record the SHA-256 that {script.name} checks"
    )


def test_the_runbook_states_the_keychain_lock_the_doctor_requires() -> None:
    lock = _shell_value(SIGNING_LIB, "release_keychain_lock_seconds")
    stated = re.findall(r"set-keychain-settings -l -u -t (\d+)", RUNBOOK.read_text())
    assert stated, "the runbook no longer gives O1's set-keychain-settings command"
    assert set(stated) == {lock}, (
        f"the runbook's set-keychain-settings uses {sorted(set(stated))}, and "
        f"release_keychain_lock_seconds in signing-lib.sh is {lock}"
    )
