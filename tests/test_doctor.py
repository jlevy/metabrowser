"""The setup checks of ``metab --doctor`` (``cli/doctor.py``) and the upgrade steps they name.

``tests/golden/cli-doctor.tryscript.md`` runs them end to end with a stand-in Git; these
cover what a transcript cannot set up: how ``metab`` was installed, the app's minimum,
and the package manager each tool's path names.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from metabrowser.builtin_plugins.github import gh_status
from metabrowser.builtin_plugins.github.gh_status import (
    GH_MINIMUM_LABEL,
    INSTALL_PAGE,
    gh_below_minimum,
    gh_upgrade_fix,
)
from metabrowser.cli import doctor
from metabrowser.cli.doctor import (
    METAB_UPGRADE_COMMANDS,
    PIPX_METADATA,
    UV_RECEIPT,
    Check,
    meets_release,
    metab_check,
    metab_install,
    metab_upgrade_remedy,
)
from metabrowser.git.process import GIT_DOWNLOAD_PAGE, git_upgrade_remedy
from metabrowser.tool_install import Remedy, install_method


@pytest.mark.parametrize(
    ("version", "minimum", "meets"),
    [
        ("0.13.0", "0.13.0", True),
        # A checkout's development build of the minimum meets it, as the app's
        # `MetabRequirement.accepts` holds.
        ("0.13.0.dev214+8b0603f7", "0.13.0", True),
        ("0.13.1", "0.13.0", True),
        ("1.0", "0.13.0", True),
        ("0.12.1.dev38+5f0c2a1", "0.13.0", False),
        ("0.12.0", "0.13.0", False),
        ("not a version", "0.13.0", None),
    ],
)
def test_a_release_meets_a_minimum_by_its_release_numbers(
    version: str, minimum: str, meets: bool | None
) -> None:
    assert meets_release(version, minimum) is meets


def _prefix(monkeypatch: pytest.MonkeyPatch, prefix: Path, checkout: Path | None) -> None:
    monkeypatch.setattr(sys, "prefix", str(prefix))
    monkeypatch.setattr(doctor, "source_checkout", lambda: checkout)


def test_a_uv_tool_install_is_known_by_its_receipt_before_a_checkout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``uv tool install --editable`` makes both a receipt and a checkout's source."""

    (tmp_path / UV_RECEIPT).write_text("[tool]\n", encoding="utf-8")
    _prefix(monkeypatch, tmp_path, tmp_path / "checkout")
    assert metab_install() == ("uv_tool", tmp_path)


def test_a_pipx_install_is_known_by_its_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / PIPX_METADATA).write_text("{}", encoding="utf-8")
    _prefix(monkeypatch, tmp_path, None)
    assert metab_install() == ("pipx", tmp_path)


def test_a_checkout_and_any_other_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    checkout = tmp_path / "metabrowser"
    _prefix(monkeypatch, tmp_path / ".venv", checkout)
    assert metab_install() == ("checkout", checkout)
    _prefix(monkeypatch, tmp_path / "venv", None)
    assert metab_install() == ("environment", tmp_path / "venv")


@pytest.mark.parametrize(
    ("method", "command"),
    [
        ("uv_tool", "uv tool install --upgrade 'metabrowser>=0.13.0'"),
        ("pipx", "pipx install --force 'metabrowser>=0.13.0'"),
        ("checkout", "git pull && make install"),
        ("environment", "uv tool install --upgrade 'metabrowser>=0.13.0'"),
    ],
)
def test_each_install_method_has_its_own_upgrade(method: str, command: str, tmp_path: Path) -> None:
    assert method in METAB_UPGRADE_COMMANDS
    remedy = metab_upgrade_remedy(method, tmp_path, "0.13.0")  # pyright: ignore[reportArgumentType]
    assert remedy.command == command
    if method == "checkout":
        assert remedy.text == f"At the root of the checkout {tmp_path}:"


def _metab(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, version: str) -> None:
    (tmp_path / UV_RECEIPT).write_text("[tool]\n", encoding="utf-8")
    _prefix(monkeypatch, tmp_path, None)
    monkeypatch.setattr(doctor, "__version__", version)
    monkeypatch.setattr(doctor, "display_version", lambda shown: shown)


def test_a_metab_older_than_the_apps_minimum_is_a_warning_with_its_upgrade(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _metab(monkeypatch, tmp_path, "0.12.0")
    app = "/Applications/Metabrowser.app"

    check = metab_check(app_path=app, app_minimum="0.13.0", looked_up=True)

    assert check.state == "warning"
    assert check.summary == (
        "metab 0.12.0 is older than 0.13.0, the oldest the app at "
        "/Applications/Metabrowser.app runs"
    )
    assert ("app", f"{app} runs metab 0.13.0 or later") in check.details
    assert check.remedy == Remedy(
        "Upgrade the uv tool install:", command="uv tool install --upgrade 'metabrowser>=0.13.0'"
    )
    assert check.problem is None, "a warning never changes the doctor's exit status"


def test_a_metab_the_app_runs_and_one_with_no_app_to_compare(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _metab(monkeypatch, tmp_path, "0.13.0.dev5+abc1234")
    app = "/Applications/Metabrowser.app"

    runs = metab_check(app_path=app, app_minimum="0.13.0", looked_up=True)
    assert (runs.state, runs.summary, runs.remedy) == (
        "ok",
        "metab 0.13.0.dev5+abc1234, which the app runs",
        None,
    )
    unnamed = metab_check(app_path=app, app_minimum=None, looked_up=True)
    assert ("app", f"{app} names no minimum metab") in unnamed.details
    assert unnamed.state == "ok"
    none = metab_check(app_path=None, app_minimum=None, looked_up=True)
    assert ("app", "none that takes a target") in none.details
    skipped = metab_check(app_path=None, app_minimum=None, looked_up=False)
    assert ("app", "not looked for") in skipped.details


def test_a_check_prints_its_state_details_and_fix() -> None:
    check = Check(
        "git",
        "Git",
        "warning",
        "git version 2.39.5 is below the floor",
        (("executable", "/usr/bin/git"),),
        Remedy("Install Git with Homebrew.", command="brew install git"),
    )
    assert check.lines() == (
        "git: warning: git version 2.39.5 is below the floor",
        "  executable: /usr/bin/git",
        "  fix: Install Git with Homebrew. brew install git",
    )
    assert check.to_json() == {
        "id": "git",
        "title": "Git",
        "state": "warning",
        "summary": "git version 2.39.5 is below the floor",
        "details": [{"name": "executable", "value": "/usr/bin/git"}],
        "remedy": {
            "text": "Install Git with Homebrew.",
            "command": "brew install git",
            "url": None,
        },
    }
    problem = Check("cache", "Cache", "problem", "not writable")
    assert problem.problem == "cache: not writable"


def _link(tmp_path: Path, real: str, name: str) -> str:
    """A ``bin/<name>`` link to *real* under *tmp_path*, as a package manager makes one."""

    target = tmp_path / real.lstrip("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("", encoding="utf-8")
    link = tmp_path / "bin" / name
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)
    return str(link)


def test_homebrew_is_known_by_its_cellar_through_the_link(tmp_path: Path) -> None:
    gh = _link(tmp_path, "opt/homebrew/Cellar/gh/2.98.0/bin/gh", "gh")
    git = _link(tmp_path, "opt/homebrew/Cellar/git/2.50.1/bin/git", "git")
    assert install_method(gh) == install_method(git) == "homebrew"
    assert gh_upgrade_fix(gh) == "brew upgrade gh"
    assert git_upgrade_remedy(git) == Remedy("Upgrade Homebrew's Git.", command="brew upgrade git")


def test_macports_and_any_other_install(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("os.path.realpath", lambda path: path)
    assert install_method("/opt/local/bin/gh") == "macports"
    assert gh_upgrade_fix("/opt/local/bin/gh") == "sudo port upgrade gh"
    assert git_upgrade_remedy("/opt/local/bin/git").command == "sudo port upgrade git"
    assert install_method("/srv/tools/bin/gh") == "other"
    assert gh_upgrade_fix("/srv/tools/bin/gh") == INSTALL_PAGE
    other = git_upgrade_remedy("/srv/tools/bin/git")
    assert (other.command, other.url) == (None, GIT_DOWNLOAD_PAGE)
    assert git_upgrade_remedy(None).url == GIT_DOWNLOAD_PAGE


@pytest.mark.parametrize(
    "path",
    [
        "/usr/bin/git",
        "/Library/Developer/CommandLineTools/usr/bin/git",
        "/Applications/Xcode.app/Contents/Developer/usr/bin/git",
    ],
)
def test_apples_git_is_replaced_with_homebrews(monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    monkeypatch.setattr("os.path.realpath", lambda found: found)
    monkeypatch.setattr(sys, "platform", "darwin")
    assert install_method(path) == "apple"
    assert git_upgrade_remedy(path).command == "brew install git"
    monkeypatch.setattr(sys, "platform", "linux")
    assert install_method(path) == "other"


@pytest.mark.parametrize(
    ("version", "below"),
    [
        ("2.80.0", True),
        ("2.20.2", True),
        (GH_MINIMUM_LABEL, False),
        ("2.98.0", False),
        ("3.0", False),
        # A version without release numbers is left to the probe.
        ("devel", False),
        (None, False),
    ],
)
def test_ghs_version_is_compared_with_the_one_minimum(version: str | None, below: bool) -> None:
    assert gh_below_minimum(version) is below


def test_ghs_minimum_is_the_release_that_added_auth_status_json() -> None:
    """2.81.0 added ``gh auth status --json`` (cli/cli#11544), which every check runs."""

    assert gh_status.GH_MINIMUM == (2, 81, 0)
    assert GH_MINIMUM_LABEL == "2.81.0"
