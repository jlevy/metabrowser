"""The keys the shell reserves, and the rule a view's declared key follows.

A view of a multi-view kind declares a one-letter ``key`` in its manifest ``[[view]]``,
and the file envelope serves it as ``views[].key``. Keys are stored lowercase and
compared without case, because a shortcut means the same with or without Shift.

The rule has two levels. :func:`view_key_error` judges one key alone, which is all one
manifest can know: it must be one letter, and not a key the shell reserves everywhere.
:func:`check_view_keys` judges a kind's merged view list, which spans manifests: a key
the shell reserves for that kind, or one an earlier view already holds, is dropped from
the later view. The server serves what it returns, and ``metab --doctor`` and
``tests/test_keymap.py`` report what it drops. Last, :func:`live_view_keys` removes
every key from a served list that kept fewer than two views, since one view has no other
tab to switch to.

The shell serves the reserved table to the browser through ``METABROWSER_SETTINGS``
(:func:`serialize_reserved_shell_keys`), so the plugin shortcut facade refuses the same
letters the manifest loader does.

``docs/design-system.md``, "Keyboard Shortcuts", is the one reference for the scheme:
letters name known meanings and mean the same wherever they are pressed, the digits 1 to
9 number the situational links and actions on a screen in reading order, and ancillary
actions such as copying have no key. ``tests/test_keymap.py`` holds that section's
table to this one and to the keys the registry registers.

This module imports nothing beyond the standard library, so the manifest loader and
``metab --doctor`` can use it without loading content classification or the server.
``docs/plugins.md`` documents the manifest field for plugin authors.
"""

from __future__ import annotations

import string
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final


@dataclass(frozen=True, slots=True)
class ReservedKey:
    """What a reserved shell key does, and the kinds it is reserved for."""

    purpose: str
    # None reserves the key for every kind. A key live only in some contexts is
    # still reserved everywhere unless it is listed with kinds here, so a shell key
    # never means one thing in one place and another elsewhere.
    kinds: frozenset[str] | None = None


# The shell's own keys, which no view may take. Each letter is a known meaning that holds
# wherever it is live, so it is reserved everywhere, even where it does nothing: `j` and
# `k` move a row down and up, and `n` and `p` go to the next and previous item one
# level up, such as the pull requests of a stack. The digits 1 to 9 are the situational
# numbers, which the registry hands out by place on screen (static/keyboard-shortcuts.js,
# `attachNumbered`), so no view or plugin names one.
RESERVED_SHELL_KEYS: Final[Mapping[str, ReservedKey]] = MappingProxyType(
    {
        "f": ReservedKey("Files tab"),
        "r": ReservedKey("Pulls tab"),
        "h": ReservedKey("Commits tab"),
        "t": ReservedKey("Quick Search"),
        "j": ReservedKey("next row"),
        "k": ReservedKey("previous row"),
        "n": ReservedKey("next item"),
        "p": ReservedKey("previous item"),
        "u": ReservedKey("parent folder command"),
        "w": ReservedKey("branch or tag switcher"),
        **{digit: ReservedKey("situational numbers") for digit in "123456789"},
    }
)


def serialize_reserved_shell_keys() -> dict[str, list[str] | None]:
    """Return the reserved table as the browser reads it from ``METABROWSER_SETTINGS``.

    Each key maps to the sorted kinds it is reserved for, or None for every kind. The
    plugin shortcut facade (``static/plugin-shortcuts.js``) refuses every key here,
    contextual ones included, because it cannot know which kinds a plugin view shows in.
    """
    return {
        key: None if reserved.kinds is None else sorted(reserved.kinds)
        for key, reserved in RESERVED_SHELL_KEYS.items()
    }


def reserved_keys_for(kind: str) -> frozenset[str]:
    """Return the shell keys reserved for *kind*: every-kind keys and its contextual ones."""
    return frozenset(
        key
        for key, reserved in RESERVED_SHELL_KEYS.items()
        if reserved.kinds is None or kind in reserved.kinds
    )


def _key_reason(key: str, kind: str | None) -> str | None:
    """Why *key* cannot be a view key, or None; *kind* None judges it for every kind."""
    if len(key) != 1 or key not in string.ascii_letters:
        return "is not one letter a-z"
    reserved = RESERVED_SHELL_KEYS.get(key.lower())
    if reserved is None:
        return None
    if reserved.kinds is None or (kind is not None and kind in reserved.kinds):
        return f"is reserved for the shell's {reserved.purpose}"
    return None


def view_key_error(key: str) -> str | None:
    """Return why *key* can be no view's key in any kind, or None when it can be one."""
    reason = _key_reason(key, None)
    return None if reason is None else f"key {key!r} {reason}"


@dataclass(frozen=True, slots=True)
class ViewKeyProblem:
    """A declared view key the merged list dropped, and why.

    *holder* is the id of the earlier view that keeps the key when the key is a
    duplicate, and None when the key was dropped for itself.
    """

    kind: str
    view_id: str
    key: object
    reason: str
    holder: str | None = None

    def describe(self, holder_plugin: str | None = None) -> str:
        """Say which key was dropped and why, naming the holder's plugin when given."""
        reason = self.reason if self.holder is None else _held_by(self.holder, holder_plugin)
        return (
            f"view {self.view_id!r} of kind {self.kind!r} declares key {self.key!r}, "
            f"{reason}; the view is served without a key"
        )

    def __str__(self) -> str:
        return self.describe()


def _held_by(view_id: str, plugin: str | None = None) -> str:
    """The reason a duplicate key gives: the earlier view, and its plugin, hold it."""
    owner = f" (plugin {plugin!r})" if plugin is not None else ""
    return f"but view {view_id!r}{owner} already holds it"


@dataclass(frozen=True, slots=True)
class ViewKeyCheck:
    """A kind's views with every rule-breaking key removed, and what was removed."""

    views: list[dict[str, Any]]
    problems: list[ViewKeyProblem]


def check_view_keys(kind: str, views: Iterable[Mapping[str, Any]]) -> ViewKeyCheck:
    """Apply the view key rule to one kind's merged view list, in tab order.

    A key survives when it is one letter, is not reserved for *kind*, and no earlier
    view holds it, compared without case; it is served lowercase. Any other key is
    removed from its view, so the first view keeps a contested letter, and each removal
    is reported. A view is never dropped for its key.
    """
    out: list[dict[str, Any]] = []
    problems: list[ViewKeyProblem] = []
    holders: dict[str, str] = {}
    for view in views:
        entry = dict(view)
        out.append(entry)
        if "key" not in entry:
            continue
        key = entry["key"]
        view_id = str(entry.get("id", "?"))
        reason = _key_reason(key, kind) if isinstance(key, str) else "is not one letter a-z"
        holder: str | None = None
        if reason is not None:
            reason = f"which {reason}"
        elif key.lower() in holders:
            holder = holders[key.lower()]
            reason = _held_by(holder)
        if reason is not None:
            del entry["key"]
            problems.append(
                ViewKeyProblem(kind=kind, view_id=view_id, key=key, reason=reason, holder=holder)
            )
            continue
        entry["key"] = key.lower()
        holders[key.lower()] = view_id
    return ViewKeyCheck(views=out, problems=problems)


# The shell draws a view tab bar for every file, but ``renderFile`` in ``static/app.js``
# gives its tabs their keys only in a bar at least this long: a lone tab has no other
# view to switch to.
MIN_TABBED_VIEWS: Final = 2


def live_view_keys(views: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return *views* with every ``key`` removed when fewer than two views remain.

    A view key switches to its view's tab, and a lone view's tab is the one already
    shown, so its key would advertise a shortcut that does nothing. Filters that run
    after :func:`check_view_keys`, such as the html kind's capability gate and a Git
    folder's Overview without a treemap, can leave one view of a multi-view kind; every
    served view list ends here, so a served key is always a live one. Removing it is
    not a problem to report: the manifest declared it correctly, and the same kind
    serves it wherever two views remain.
    """
    if len(views) >= MIN_TABBED_VIEWS:
        return views
    return [{name: value for name, value in view.items() if name != "key"} for view in views]
