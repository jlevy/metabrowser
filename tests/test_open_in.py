"""The ``open_in`` preference: where it is read, and the light reader of ``config.yml``.

``metabrowser.open_in`` reads the one setting without the record's contract, so these
tests hold it to the contract's reader, ``read_config`` in ``cache/layout.py``, for every
value the setting may hold.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

import pytest

from metabrowser.cache.layout import (
    CONFIG_FORMAT,
    ConfigurationError,
    read_config,
    serialize_config,
)
from metabrowser.cache.records import ApplicationConfig
from metabrowser.config_file import CONFIG_MAX_BYTES, CONFIG_RECORD
from metabrowser.home import (
    PrivateStorageError,
    configuration_directory,
    ensure_private_directory,
    write_private_file_atomic,
)
from metabrowser.open_in import (
    DEFAULT_OPEN_IN,
    OPEN_IN_CHOICES,
    OPEN_IN_ENV,
    OpenInError,
    OpenInPreference,
    configured_open_in,
    parse_open_in,
    resolve_open_in,
)

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only storage is POSIX-only")

_HEADER: Final = (
    "softschema:\n"
    "  contract: metabrowser.config:ApplicationConfig/v1\n"
    "  envelope: config\n"
    "  status: permissive\n"
)
_SETTINGS: Final = "config:\n  format: f01\n  written_by: 0.13.0\n  upgrades: []\n"


def _home() -> Path:
    directory = configuration_directory()
    ensure_private_directory(directory)
    return directory


def _write(text: str) -> Path:
    home = _home()
    write_private_file_atomic(home, CONFIG_RECORD, text.encode())
    return home


def test_the_choices_and_the_default() -> None:
    assert OPEN_IN_CHOICES == ("auto", "app", "browser")
    assert DEFAULT_OPEN_IN == "auto"
    assert [parse_open_in(value) for value in OPEN_IN_CHOICES] == list(OPEN_IN_CHOICES)
    assert [parse_open_in(value) for value in ("", "App", " app", None, 1, ["app"])] == [None] * 6


@posix_only
@pytest.mark.parametrize(
    ("flag", "environment", "configured", "expected"),
    [
        ("app", "browser", "browser", OpenInPreference("app", "flag")),
        (None, "browser", "app", OpenInPreference("browser", "environment")),
        (None, "", "app", OpenInPreference("app", "config")),
        (None, None, "browser", OpenInPreference("browser", "config")),
        (None, None, None, OpenInPreference("auto", "default")),
    ],
)
def test_the_flag_then_the_environment_then_config_yml_choose(
    flag: str | None,
    environment: str | None,
    configured: str | None,
    expected: OpenInPreference,
) -> None:
    if configured is not None:
        _write(_HEADER + _SETTINGS + f"  open_in: {configured}\n")
    environ = {} if environment is None else {OPEN_IN_ENV: environment}
    assert resolve_open_in(flag, environ=environ) == expected


def test_a_preference_that_is_not_a_choice_is_refused_where_it_was_read() -> None:
    with pytest.raises(OpenInError, match=r"^--open-in 'sometimes' is not auto, app, or browser$"):
        resolve_open_in("sometimes", environ={})
    with pytest.raises(OpenInError) as raised:
        resolve_open_in(None, environ={OPEN_IN_ENV: "App"})
    assert str(raised.value) == (
        f"{OPEN_IN_ENV} is not auto, app, or browser; set it to one, or unset it"
    )


@posix_only
def test_no_configuration_and_a_file_without_the_setting_read_as_unset(tmp_path: Path) -> None:
    assert configured_open_in(tmp_path / "missing") is None
    assert configured_open_in() is None
    home = _write(_HEADER + _SETTINGS)
    assert configured_open_in(home) is None
    _write(_HEADER + _SETTINGS + "  open_in: null\n")
    assert configured_open_in() is None


@posix_only
@pytest.mark.parametrize(
    ("text", "complaint"),
    [
        (
            _HEADER + _SETTINGS + "  open_in: sometimes\n",
            "open_in in {path} is not auto, app, or browser",
        ),
        (
            _HEADER + _SETTINGS + "  open_in: [app]\n",
            "open_in in {path} is not auto, app, or browser",
        ),
        (_HEADER + _SETTINGS + "  open_in: 1\n", "open_in in {path} is not auto, app, or browser"),
        ("config: [\n", "{path} is not YAML"),
        ("- open_in: app\n", "{path} has no config mapping"),
        (_HEADER + "config: app\n", "{path} has no config mapping"),
    ],
)
def test_a_config_yml_it_cannot_read_is_an_error_that_names_the_file_and_the_fix(
    text: str, complaint: str
) -> None:
    home = _write(text)
    path = home / CONFIG_RECORD
    with pytest.raises(OpenInError) as raised:
        resolve_open_in(None, environ={})
    assert str(raised.value) == (
        complaint.format(path=path)
        + "; fix open_in there, or choose with --open-in or METABROWSER_OPEN_IN, "
        "which are read first"
    )
    # The flag and the environment are read first, so either still chooses.
    assert resolve_open_in("browser", environ={}) == OpenInPreference("browser", "flag")
    assert resolve_open_in(None, environ={OPEN_IN_ENV: "app"}) == OpenInPreference(
        "app", "environment"
    )


@posix_only
def test_a_config_yml_past_its_bound_is_not_read() -> None:
    settings = "".join(f"  k{index:06d}: v\n" for index in range(3000))
    home = _write(_HEADER + _SETTINGS + "  open_in: app\n" + settings)
    path = home / CONFIG_RECORD
    assert path.stat().st_size > CONFIG_MAX_BYTES
    with pytest.raises(OpenInError, match="is larger than 16384 bytes, so it is not read"):
        configured_open_in()


@posix_only
def test_a_config_yml_others_can_read_is_read_and_left_as_it_is() -> None:
    """The preference is a read that changes nothing on disk, as ``shared="keep"`` says."""

    home = _write(_HEADER + _SETTINGS + "  open_in: app\n")
    (home / CONFIG_RECORD).chmod(0o644)
    assert configured_open_in() == "app"
    assert (home / CONFIG_RECORD).stat().st_mode & 0o777 == 0o644


@posix_only
def test_a_config_yml_that_is_a_link_is_refused_as_the_full_reader_refuses_it(
    tmp_path: Path,
) -> None:
    elsewhere = tmp_path / "elsewhere.yml"
    elsewhere.write_text(_HEADER + _SETTINGS + "  open_in: app\n")
    home = _home()
    (home / CONFIG_RECORD).symlink_to(elsewhere)
    with pytest.raises(OpenInError, match=r"Or choose with --open-in or METABROWSER_OPEN_IN\.$"):
        configured_open_in()
    with pytest.raises(PrivateStorageError):
        read_config(home, shared="keep")


# ── The light reader answers as the contract's reader does ──────────


@posix_only
@pytest.mark.parametrize("choice", [*OPEN_IN_CHOICES, None])
def test_the_light_reader_reads_what_the_contract_writes(choice: str | None) -> None:
    config = ApplicationConfig.model_validate(
        {"format": CONFIG_FORMAT, "written_by": "0.13.0", "upgrades": [], "open_in": choice}
    )
    home = _home()
    write_private_file_atomic(home, CONFIG_RECORD, serialize_config(config))
    read = read_config(home, shared="keep")
    assert read is not None
    assert read.open_in == choice == configured_open_in(home)


def test_an_unset_open_in_is_written_as_no_key() -> None:
    """A config this release writes, which sets nothing, gains no ``open_in: null``."""

    config = ApplicationConfig(format=CONFIG_FORMAT, written_by="0.13.0", upgrades=[])
    assert config.open_in is None
    assert "open_in" not in config.model_dump(mode="json")
    assert b"open_in" not in serialize_config(config)
    chosen = config.model_copy(update={"open_in": "browser"})
    assert chosen.model_dump(mode="json")["open_in"] == "browser"


@posix_only
@pytest.mark.parametrize("value", ["sometimes", "[app]", "1", "''"])
def test_both_readers_refuse_a_value_that_is_not_a_choice(value: str) -> None:
    home = _write(_HEADER + _SETTINGS + f"  open_in: {value}\n")
    with pytest.raises(ConfigurationError):
        read_config(home, shared="keep")
    with pytest.raises(OpenInError):
        configured_open_in(home)
