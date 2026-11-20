"""Immutable content-trust capabilities resolved once per process.

The server is authoritative. Client settings and ``/api/capabilities``
publish the same block as a hint. ``--untrusted`` sets every switch to
its conservative value; individual CLI flags override that profile, and
nothing in the environment does.

The block is the process's and says how the reader trusts the files they opened. A
pinned Git revision is never served under it: its content is whatever its repository
holds, so every route that answers a pin uses :data:`UNTRUSTED_CAPABILITIES`, chosen by
the subject the request resolved and not by anything read later
(:func:`capabilities_for`).
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

``metabrowser.dotenv`` loads only its own allowlist, so a name added here is
outside that list and cannot arrive from a browsed repository's ``.env``.
That module raises at import if the two sets ever overlap."""

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
# Every switch at its conservative value: what ``--untrusted`` resolves to, and what a
# pinned revision is always served under.
UNTRUSTED_CAPABILITIES = Capabilities(active_content=False, mutations=False)
_current = DEFAULT_CAPABILITIES


def get_capabilities() -> Capabilities:
    """The process's block: how the reader trusts the folder they opened."""

    return _current


def capabilities_for(*, pinned_revision: bool) -> Capabilities:
    """The block a request is answered under, by the subject it resolved.

    A pinned revision is never trusted, whatever the process's block: a mirror's content
    is its origin's, and a branch or tag in a checkout's ``.git`` is whatever a fetch
    brought, where the folder is what the reader works in. A caller passes whether the
    subject it resolved *at the start of the request* is a pin, and uses the answer for
    the whole request, so a switch of the served subject while the request awaits cannot
    render a revision's content under the folder's profile. A server showing a revision
    of its own checkout therefore needs no flag: the folder's profile is simply what its
    working tree's requests get.
    """

    return UNTRUSTED_CAPABILITIES if pinned_revision else _current


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


def untrusted_shell_csp(nonce: str, origin: str, kpress_scripts: tuple[str, ...]) -> str:
    """The Content-Security-Policy of the application page when active content is off.

    Rendered Markdown is already reduced to an allowlist before it reaches the page
    (:mod:`metabrowser.inert_html`); this is the second line. Scripts run only from the
    application's own static paths on *origin* -- ``/static/`` and ``/plugin-static/``,
    never ``/raw``, where the browsed repository's own files are -- and the shell's
    inline scripts only by *nonce*; no inline handler runs. The one exception is
    *kpress_scripts*, each an exact KPress module path on *origin*: KPress's diagram
    renderer and controls and the two modules they import, which draw an inert render's
    Mermaid diagrams as images (``builtin_plugins/markdown/diagrams.js``). They are the
    installed KPress package's own code, served as ``/static/`` is, and admitted by full
    path, so no other KPress script runs over an untrusted document. Stylesheets come from those
    paths and ``/kpress-static/``; the Markdown worker from ``/plugin-static/``. Fonts
    and requests stay on this origin. Images also admit ``data:`` ones the stylesheet
    draws and GitHub's exact avatar host for application-owned author portraits;
    document images remain restricted by the markup allowlist. The page frames no URL
    -- the untrusted profile removes the HTML preview, its only framed address; its one
    frame is the ``about:srcdoc`` diagram frame, under a stricter policy of its own as
    well as this one, which admits its stylesheet from ``/plugin-static/``
    (``builtin_plugins/markdown/diagram-frame.js``) -- is framed by nothing, and has no
    plugins, ``<base>``, or form submission. Inline ``style``
    attributes stay allowed because the application writes them; an outside ``url()``
    inside one is still limited to those image origins. A ``<style>`` element is not:
    Mermaid lays each diagram out with one, so an untrusted document with diagrams logs
    one expected ``style-src-elem`` violation per diagram, which costs nothing because
    KPress's measuring host carries Mermaid's font and the image applies the style
    outside the page (``tests/dom/markdown-diagrams-chrome.mjs`` admits only those). The
    same image-origin limit bounds what an untrusted document's diagram can still load
    while Mermaid lays it out in the page, its image shape (``A@{ img: … }``) and images
    its own CSS names; a pull request's text is laid out in the diagram frame instead,
    which loads none of them.
    """

    static = f"{origin}/static/"
    plugins = f"{origin}/plugin-static/"
    kpress = f"{origin}/kpress-static/"
    return "; ".join(
        (
            "default-src 'self'",
            " ".join(
                (
                    f"script-src 'nonce-{nonce}' {static} {plugins}",
                    *(f"{origin}{path}" for path in kpress_scripts),
                )
            ),
            f"style-src {static} {plugins} {kpress}",
            "style-src-attr 'unsafe-inline'",
            "img-src 'self' data: https://avatars.githubusercontent.com",
            "font-src 'self'",
            "connect-src 'self'",
            f"worker-src {plugins}",
            "frame-src 'none'",
            "frame-ancestors 'none'",
            "object-src 'none'",
            "base-uri 'none'",
            "form-action 'none'",
        )
    )
