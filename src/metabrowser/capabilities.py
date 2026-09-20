"""Immutable content-trust capabilities resolved once per process.

The server is authoritative. Client settings and ``/api/capabilities``
publish the same block as a hint. ``--untrusted`` sets every switch to
its conservative value; individual CLI flags override that profile, and
nothing in the environment does.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})

ENV_UNTRUSTED = "METAB_UNTRUSTED"
ENV_ACTIVE_CONTENT = "METAB_ACTIVE_CONTENT"
ENV_ALLOW_EDITS = "METAB_ALLOW_EDITS"

CAPABILITY_ENV_VARS: tuple[str, ...] = (
    ENV_UNTRUSTED,
    ENV_ACTIVE_CONTENT,
    ENV_ALLOW_EDITS,
)
"""Every variable ``resolve_capabilities`` reads, named once.

``metabrowser.dotenv`` refuses this set, so the resolution below is the only
place a capability variable name is written and the refusal cannot fall behind
a variable added here."""

# Token order is the sandbox contract. Drop ``allow-scripts`` in place when
# active content is off; do not rewrite the rest of the directive.
_RAW_SANDBOX_TOKENS = (
    "sandbox",
    "allow-scripts",
    "allow-popups",
    "allow-forms",
    "allow-downloads",
)


def env_bool(name: str) -> bool | None:
    """Return a tri-state flag from *name*, or ``None`` when unset."""

    raw = os.environ.get(name)
    if raw is None:
        return None
    text = raw.strip().lower()
    if text == "":
        return None
    if text in _FALSE:
        return False
    if text in _TRUE:
        return True
    return None


@dataclass(frozen=True, slots=True)
class Capabilities:
    """Server-authoritative switches for content surfaces and mutations."""

    active_content: bool
    mutations: bool

    def as_wire(self) -> dict[str, bool]:
        return {
            "active_content": self.active_content,
            "mutations": self.mutations,
        }


DEFAULT_CAPABILITIES = Capabilities(active_content=True, mutations=False)
_current = DEFAULT_CAPABILITIES


def get_capabilities() -> Capabilities:
    return _current


def set_capabilities(capabilities: Capabilities) -> None:
    """Install the process-wide capability block. Tests reset this."""

    global _current
    _current = capabilities


def apply_capabilities(
    *,
    untrusted: bool = False,
    no_active_content: bool = False,
    allow_edits: bool = False,
) -> Capabilities:
    """Resolve and install the process capability block."""

    capabilities = resolve_capabilities(
        untrusted=untrusted,
        no_active_content=no_active_content,
        allow_edits=allow_edits,
    )
    set_capabilities(capabilities)
    return capabilities


def resolve_capabilities(
    *,
    untrusted: bool = False,
    no_active_content: bool = False,
    allow_edits: bool = False,
) -> Capabilities:
    """Resolve the process capability block from CLI flags and environment.

    Defaults: ``active_content`` on, ``mutations`` off. ``--untrusted`` /
    ``METAB_UNTRUSTED=1`` sets both conservative. ``--no-active-content`` /
    ``METAB_ACTIVE_CONTENT=0`` and ``--allow-edits`` / ``METAB_ALLOW_EDITS=1``
    then override the profile.

    A CLI flag is a decision the operator typed at the call site, so it beats
    the environment in both directions: an explicit disable beats an env
    enable, and an explicit ``--untrusted`` beats one too. Only another
    explicit flag lifts the profile, which is what ``--untrusted
    --allow-edits`` says. Within the environment alone an enable still
    overrides ``METAB_UNTRUSTED``.
    """

    profile = untrusted or bool(env_bool(ENV_UNTRUSTED))
    active_content = not profile
    mutations = False

    env_active = env_bool(ENV_ACTIVE_CONTENT)
    if no_active_content or env_active is False:
        active_content = False
    elif env_active is True and not untrusted:
        active_content = True

    if allow_edits or (env_bool(ENV_ALLOW_EDITS) is True and not untrusted):
        mutations = True

    return Capabilities(active_content=active_content, mutations=mutations)


def raw_sandbox_csp(*, active_content: bool) -> str:
    """CSP sandbox directive for ``/raw``, with scripts gated by capability."""

    return " ".join(
        token for token in _RAW_SANDBOX_TOKENS if active_content or token != "allow-scripts"
    )
