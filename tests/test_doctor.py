"""The setup checks of ``metab --doctor`` (``cli/doctor.py``) and the upgrade steps they name.

``tests/golden/cli-doctor.tryscript.md`` runs them end to end with a stand-in Git; these
cover what a transcript cannot set up: how ``metab`` was installed, the app's minimum,
and the package manager each tool's path names.
"""

from __future__ import annotations

import plistlib
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
from metabrowser.cache.free_space import FREE_SPACE_RESERVE_ENV, FREE_SPACE_RESERVE_MB
from metabrowser.cli import doctor
from metabrowser.cli.doctor import (
    CHECKOUT_PROJECT,
    CHECKOUT_VENV,
    DOCTOR_APP_ENV,
    METAB_UPGRADE_COMMANDS,
    PIPX_METADATA,
    UV_RECEIPT,
    Check,
    cache_check,
    config_check,
    declares_this_project,
    doctor_checks,
    meets_release,
    metab_check,
    metab_install,
    metab_upgrade_remedy,
    open_in_check,
    plugins_check,
    running_app,
)
from metabrowser.cli.present import MINIMUM_METAB_KEY, DoctorOpenIn
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


def _prefix(monkeypatch: pytest.MonkeyPatch, prefix: Path) -> None:
    prefix.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sys, "prefix", str(prefix))


def _project(root: Path, name: str = "metabrowser") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(f'[project]\nname = "{name}"\n', encoding="utf-8")
    return root


def test_a_uv_tool_install_is_known_by_its_receipt_before_a_checkout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``uv tool install --editable`` into a checkout's ``.venv`` makes a receipt there."""

    venv = _project(tmp_path / "metabrowser") / ".venv"
    _prefix(monkeypatch, venv)
    (venv / UV_RECEIPT).write_text("[tool]\n", encoding="utf-8")
    assert metab_install() == ("uv_tool", venv)


def test_a_pipx_install_is_known_by_its_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _prefix(monkeypatch, tmp_path)
    (tmp_path / PIPX_METADATA).write_text("{}", encoding="utf-8")
    assert metab_install() == ("pipx", tmp_path)


def test_a_checkout_is_a_venv_beside_this_projects_pyproject(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The rule ``MetabInstall.of`` reads in the app, so both name the same step."""

    checkout = _project(tmp_path / "metabrowser")
    _prefix(monkeypatch, checkout / CHECKOUT_VENV)
    assert metab_install() == ("checkout", checkout)
    # Another project's `.venv` with metabrowser installed in it is not a checkout.
    other = _project(tmp_path / "notes", name="notes")
    _prefix(monkeypatch, other / CHECKOUT_VENV)
    assert metab_install() == ("environment", other / CHECKOUT_VENV)
    # Nor is an environment named otherwise, beside this project or not.
    _prefix(monkeypatch, checkout / "venv")
    assert metab_install() == ("environment", checkout / "venv")


def test_the_project_line_is_the_one_this_repository_declares() -> None:
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    assert declares_this_project(pyproject)


@pytest.mark.parametrize(
    ("pyproject", "declares"),
    [
        ('name = "metabrowser"', True),
        ('name="metabrowser"  ', True),
        ('[project]\r\nname = "metabrowser"\r\n', True),
        ('name = "metabrowser-extras"', False),
        ('  name = "metabrowser"', False),
        ('names = "metabrowser"', False),
        ('# name = "metabrowser"', False),
        ('name\n= "metabrowser"', False),
    ],
)
def test_a_checkouts_project_is_named_on_its_own_line(pyproject: str, declares: bool) -> None:
    """The cases ``aCheckoutsProjectIsNamedOnItsOwnLine`` in ``MetabVersionTests`` reads."""

    assert (CHECKOUT_PROJECT.search(pyproject) is not None) is declares


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
    _prefix(monkeypatch, tmp_path)
    (tmp_path / UV_RECEIPT).write_text("[tool]\n", encoding="utf-8")
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


def test_the_plugins_are_a_check_with_each_problem_a_detail() -> None:
    clean = plugins_check(11, ())
    assert (clean.state, clean.summary) == (
        "ok",
        "11 plugins and the packaged cache record contracts check out",
    )
    broken = plugins_check(1, ("plugin 'x': index.js missing in /p",))
    assert broken.state == "problem"
    assert ("problem", "plugin 'x': index.js missing in /p") in broken.details
    assert broken.problem is not None, "doctor_plugins lists the details instead"


def _open_in(problems: tuple[str, ...], unread: tuple[str, ...]) -> DoctorOpenIn:
    section: dict[str, object] = {
        "value": "auto",
        "source": "default",
        "present_browser": None,
        "app": None,
    }
    return DoctorOpenIn(section, "open_in auto (default)", problems, unread)


def test_a_configuration_directory_that_is_a_problem_is_reported_once() -> None:
    """``config`` reports the directory; ``open_in`` notes what it could not read there."""

    unread = "open_in: The Metabrowser storage directory is accessible to other users"
    settled = "open_in is app (environment), and no app takes a target: none"
    check = open_in_check(_open_in((unread, settled), (unread,)), config_unreadable=True)
    assert ("not read", unread) in check.details
    assert ("problem", unread) not in check.details
    assert ("problem", settled) in check.details
    assert check.state == "problem"
    only_unread = open_in_check(_open_in((unread,), (unread,)), config_unreadable=True)
    assert only_unread.state == "warning"
    readable = open_in_check(_open_in((unread,), (unread,)), config_unreadable=False)
    assert (readable.state, ("problem", unread) in readable.details) == ("problem", True)


def _storage(monkeypatch: pytest.MonkeyPatch, home: Path, **variables: str) -> None:
    for name in ("METABROWSER_CONFIG_DIR", "XDG_CONFIG_HOME", "METABROWSER_CACHE_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setenv("HOME", str(home))
    for name, value in variables.items():
        monkeypatch.setenv(name, value)


def test_an_override_the_apps_servers_do_not_get_is_a_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The app gives its servers none of the storage variables (``ChildEnvironment``)."""

    mine = tmp_path / "xdg"
    mine.mkdir(mode=0o700)
    (mine / "metabrowser").mkdir(mode=0o700)
    _storage(monkeypatch, tmp_path / "home", XDG_CONFIG_HOME=str(mine))
    app = "/Applications/Metabrowser.app"

    check = config_check(app_path=app)
    servers = str(tmp_path / "home" / ".config" / "metabrowser")
    assert check.state == "warning"
    assert ("app's servers", servers) in check.details
    assert check.summary.startswith("XDG_CONFIG_HOME names this directory")
    assert check.remedy is not None
    assert config_check(app_path=None).state == "ok", "without an app there is nothing to differ"


_RESERVE: int = FREE_SPACE_RESERVE_MB * 1_000_000


def test_free_space_below_the_first_clone_reserve_is_a_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Below the reserve a first clone leaves free, every first clone is refused but one
    that borrows a checkout's objects, which is not checked."""

    cache = tmp_path / "cache"
    cache.mkdir(mode=0o700)
    _storage(monkeypatch, tmp_path, METABROWSER_CACHE_DIR=str(cache))
    monkeypatch.delenv(FREE_SPACE_RESERVE_ENV, raising=False)
    monkeypatch.setattr(doctor, "volume_free_bytes", lambda _directory: 400_000_000)
    low = cache_check()
    assert low.state == "warning"
    assert low.summary == (
        "the cache's volume has 400 MB free, less than the 1.0 GB a first clone leaves "
        "free, so metab refuses every first clone that does not borrow from a checkout"
    )
    assert ("free space", "400 MB") in low.details
    monkeypatch.setattr(doctor, "volume_free_bytes", lambda _directory: _RESERVE - 1)
    assert cache_check().state == "warning"
    assert low.remedy is not None and FREE_SPACE_RESERVE_ENV in low.remedy.text
    monkeypatch.setattr(doctor, "volume_free_bytes", lambda _directory: _RESERVE)
    assert cache_check().state == "ok"
    monkeypatch.setenv(FREE_SPACE_RESERVE_ENV, "0")
    monkeypatch.setattr(doctor, "volume_free_bytes", lambda _directory: 0)
    assert cache_check().state == "ok", "no reserve, so no volume refuses every clone"


def test_a_missing_cache_directory_metab_cannot_create_is_a_problem(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The host's free space is not what this test is about.
    monkeypatch.setattr(doctor, "volume_free_bytes", lambda _directory: _RESERVE)
    locked = tmp_path / "locked"
    locked.mkdir(mode=0o500)
    try:
        _storage(monkeypatch, tmp_path, METABROWSER_CACHE_DIR=str(locked / "cache"))
        check = cache_check()
        assert check.state == "problem"
        assert check.summary == (
            "the cache directory does not exist, and metab cannot create it: "
            f"{locked} is not writable by this user"
        )
        assert check.remedy == Remedy(
            "Create it with mode 700 yourself, or set METABROWSER_CACHE_DIR to a private "
            "directory you own."
        )
        _storage(monkeypatch, tmp_path, METABROWSER_CACHE_DIR=str(tmp_path / "fresh" / "cache"))
        assert cache_check().state == "ok"
    finally:
        locked.chmod(0o700)


@pytest.mark.parametrize(
    ("state", "fix", "remedy"),
    [
        ("gh_missing", INSTALL_PAGE, Remedy("Install GitHub CLI.", url=INSTALL_PAGE)),
        (
            "gh_too_old",
            "brew upgrade gh",
            Remedy("Update GitHub CLI.", command="brew upgrade gh"),
        ),
        (
            "not_logged_in",
            "gh auth login --hostname github.com",
            Remedy("Sign in to GitHub CLI.", command="gh auth login --hostname github.com"),
        ),
        # A sentence is never a command to copy.
        (
            "not_logged_in",
            "replace the token in GH_TOKEN, or unset it and run gh auth login --hostname "
            "github.com",
            Remedy(
                "Replace the token in GH_TOKEN, or unset it and run gh auth login --hostname "
                "github.com."
            ),
        ),
        ("network_error", None, None),
    ],
)
def test_githubs_remedy_names_a_command_only_for_one_it_runs(
    state: str, fix: str | None, remedy: Remedy | None
) -> None:
    status = gh_status.GithubStatus(state, "message", fix)  # pyright: ignore[reportArgumentType]
    assert status.remedy == remedy
    assert status.to_json()["remedy"] == (remedy.to_json() if remedy is not None else None)


def _bundle(root: Path, minimum: str | None) -> Path:
    contents = root / "Metabrowser.app" / "Contents"
    contents.mkdir(parents=True)
    info: dict[str, object] = {"CFBundleIdentifier": "io.github.jlevy.metabrowser.dev"}
    if minimum is not None:
        info[MINIMUM_METAB_KEY] = minimum
    (contents / "Info.plist").write_bytes(plistlib.dumps(info))
    return root / "Metabrowser.app"


def test_the_metab_check_compares_with_the_app_running_the_check(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Check Setup… names its own build, which LaunchServices may not find first."""

    running = _bundle(tmp_path / "build", "99.0.0")
    monkeypatch.setenv(DOCTOR_APP_ENV, str(running))
    assert running_app() == (str(running), "99.0.0")
    _storage(monkeypatch, tmp_path / "home")
    checks = doctor_checks(plugin_count=1, plugin_problems=(), open_in=_open_in((), ()))
    metab = next(check for check in checks if check.id == "metab")
    assert metab.state == "warning"
    assert ("app", f"{running} runs metab 99.0.0 or later") in metab.details
    open_in = next(check for check in checks if check.id == "open_in")
    assert open_in.summary == "open_in auto (default)", "a terminal's lookup is unchanged"


def test_a_running_app_the_doctor_cannot_read_is_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for named in ("", "relative/Metabrowser.app", str(tmp_path / "missing.app")):
        monkeypatch.setenv(DOCTOR_APP_ENV, named)
        assert running_app() is None
    monkeypatch.setenv(DOCTOR_APP_ENV, str(_bundle(tmp_path, None)))
    assert running_app() == (str(tmp_path / "Metabrowser.app"), None)


@pytest.mark.parametrize(("variable", "unread"), [("sometimes", False), (None, True)])
def test_only_a_setting_config_yml_could_not_give_is_unread(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, variable: str | None, unread: bool
) -> None:
    """``METABROWSER_OPEN_IN`` is read before ``config.yml``, so its error is its own,
    which the ``config`` check never reports for it."""

    from metabrowser.cli import present

    shared = tmp_path / "shared"
    shared.mkdir(mode=0o755)
    shared.chmod(0o755)
    _storage(monkeypatch, tmp_path, METABROWSER_CONFIG_DIR=str(shared))
    if variable is None:
        monkeypatch.delenv("METABROWSER_OPEN_IN", raising=False)
    else:
        monkeypatch.setenv("METABROWSER_OPEN_IN", variable)
    monkeypatch.setattr(present, "look_up_app", lambda _ids: None)
    report = present.doctor_open_in()
    first = report.problems[0]
    assert first.startswith("open_in: ")
    assert (first in report.unread) is unread
