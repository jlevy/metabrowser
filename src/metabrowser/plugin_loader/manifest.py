"""Plugin manifest schema.

A metabrowser plugin is a directory containing ``manifest.toml`` (this
schema) and an ``index.js`` (the JS module the shell dynamically imports
at startup). Optional Python sidekicks register HTTP handlers under
``/api/plugin/<plugin>/<route>`` for server-side data hooks.

A plugin's directory layout::

    my-plugin/
    ├── manifest.toml         # this schema
    ├── index.js              # registers detectors/views via window.metabrowser
    ├── sidekick.py           # optional — Python handlers for [[data_hook]] routes
    ├── styles.css            # optional — CSS scoped under .mb-plugin-<name>
    └── *.mustache, *.svg     # optional — fetched by index.js as needed

The shell never executes the manifest as code; it's parsed via the
stdlib ``tomllib`` reader and validated by the Pydantic models below.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from metabrowser.content_sniff import SNIFF_PREFIX_BYTES
from metabrowser.keymap import view_key_error

# SDK contract version

# The browser SDK contract this host provides. A plugin declares the
# contract it was written against and the loader rejects any other value,
# so an SDK break surfaces as one clear message at load time instead of a
# mystery failure inside a renderer.
#
# Bump this only when the contract actually breaks, and update every
# built-in manifest in the same commit. The host ships no shims for older
# values: an external plugin is expected to update and declare it. See
# docs/development.md "Compatibility and Legacy Code".
PLUGIN_SDK_VERSION = "0.8"

# Metabrowser 0.4.0 allowed manifests to omit sdk_version. Such a manifest
# targets the only SDK that existed under that contract. Keep this value pinned
# when PLUGIN_SDK_VERSION changes so omission fails the ordinary mismatch gate.
_IMPLICIT_PLUGIN_SDK_VERSION = "0.1"

# A Python distribution's name as PEP 508 allows one, without a version or extras.
_DISTRIBUTION_NAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")


def normalize_distribution(name: str) -> str:
    """A distribution name as PEP 503 compares them: lowercase, runs of ``-_.`` as ``-``."""

    return re.sub(r"[-_.]+", "-", name).lower()


# A plugin's name, which is also how another plugin's ``requires`` names it.
_PLUGIN_NAME = re.compile(r"^[a-z][a-z0-9_-]*$")

# ── Match predicate ────────────────────────────────────────────

# The furthest byte a `magic` rule may name: the sniff prefix every classification site
# already holds when it falls back to `binary` (`SNIFF_PREFIX_BYTES` in
# `metabrowser.content_sniff`), so a magic check never costs a read of its own.
MAGIC_MAX_END = SNIFF_PREFIX_BYTES


class MagicMatch(BaseModel):
    """Bytes a binary format holds at a fixed offset, as ``magic = {offset, hex}``.

    ``hex`` spells the bytes in hexadecimal, since a format's magic is often not text
    (and a TOML string would encode a byte past 0x7f as two).
    """

    model_config = ConfigDict(extra="forbid")

    offset: int = Field(default=0, ge=0, description="Where the bytes start in the file.")
    hex: str = Field(..., description="The bytes expected there, in hexadecimal.")

    @field_validator("hex")
    @classmethod
    def _hex_bytes(cls, value: str) -> str:
        try:
            raw = bytes.fromhex(value)
        except ValueError:
            raise ValueError(f"magic.hex {value!r} is not hexadecimal bytes") from None
        if not raw:
            raise ValueError("magic.hex names no bytes")
        return raw.hex()

    @property
    def expected(self) -> bytes:
        return bytes.fromhex(self.hex)

    def matches(self, prefix: bytes) -> bool:
        """Whether *prefix*, a file's leading bytes on disk, holds these bytes."""
        expected = self.expected
        return prefix[self.offset : self.offset + len(expected)] == expected


class KindMatch(BaseModel):
    """Declarative file-classification predicate.

    Every field is optional; the classifier evaluates the predicate as the
    AND of every set field. At least one field must be set or the rule is
    rejected at validation time.
    """

    model_config = ConfigDict(extra="forbid")

    ext: str | None = Field(
        default=None, description="Match files with this extension (include the dot)."
    )
    exts: list[str] | None = Field(
        default=None,
        description=(
            "Match files whose extension is in this list (include the dot on each entry). "
            "Mutually exclusive with ``ext``; set one or the other, not both."
        ),
    )
    basename: str | None = Field(
        default=None, description="Match files whose basename equals this exactly."
    )
    frontmatter_has_key: str | None = Field(
        default=None,
        description="Match .md files whose YAML frontmatter contains this top-level key.",
    )
    frontmatter_schema_prefix: str | None = Field(
        default=None,
        description=(
            "Match .md files whose frontmatter has a `schema:` value starting with this string."
        ),
    )
    adapter: str | None = Field(
        default=None,
        description="Match .jsonl files whose adapter sniff returns this value.",
    )
    json_has_key: str | None = Field(
        default=None,
        description="Match .json files whose top-level object has this key.",
    )
    json_value_prefix: str | None = Field(
        default=None,
        description=(
            "Used with `json_has_key`: require the value to be a string starting with this prefix."
        ),
    )
    yaml_has_key: str | None = Field(
        default=None,
        description=(
            "Match .yaml/.yml files whose top-level mapping contains this key. "
            "Parsed via a bounded prefix read so multi-MB files do not slow the classifier."
        ),
    )
    yaml_value_prefix: str | None = Field(
        default=None,
        description=(
            "Used with `yaml_has_key`: require the value of that key to be a string starting "
            "with this prefix."
        ),
    )
    folder_marker: str | None = Field(
        default=None,
        description=(
            "Match a file whose basename equals this value AND register the parent directory "
            "as marker-bearing so the tree renderer paints a badge. Equivalent to `basename = "
            "<value>` for classification purposes; the value of spelling it separately is the "
            "tree-row decoration."
        ),
    )
    path_glob: str | None = Field(
        default=None,
        description=(
            "Match files whose served-root-relative path matches this gitignore-style glob "
            "(e.g. `**/files/derived/**/*.md`). Backed by pathspec; combines with the other "
            "match.* fields by AND."
        ),
    )
    magic: MagicMatch | None = Field(
        default=None,
        description=(
            "Match a file that would otherwise be `binary` whose bytes on disk hold these "
            "bytes at this offset, whatever its name. Only `ext` or `exts` may be set "
            "beside it: they decide the tree's container chevron, and a file with one of "
            "those extensions that sniffs as text is also matched when its leading bytes "
            "hold these, as an ASCII PDF named `.pdf` is."
        ),
    )

    def is_empty(self) -> bool:
        """Return True if no predicate fields are set."""
        return all(getattr(self, f) is None for f in type(self).model_fields)


# ── Kind, view, data_hook ──────────────────────────────────────


class ContainerSpec(BaseModel):
    """The ``container`` table on a ``[[kind]]`` — folder-like behavior.

    A container kind's files play both nav-tree roles from
    ``docs/project/architecture/arch-plugin-system.md``: item-like
    (selecting the file opens its normal views — the overview) and
    folder-like (the row expands to child entries). Children come from
    the named data hook; a child's document is served by the same kind's
    views for the virtual path ``<file>/<inner>``, which the server
    resolves by nearest-file-ancestor.
    """

    model_config = ConfigDict(extra="forbid")

    children: str = Field(
        ...,
        description=(
            "data_hook route (this plugin's) returning tree child entries for "
            "?path=<container file>. Response shape: {children: [{name, path, "
            "badge?, muted?}]} where path is the virtual child path."
        ),
    )


class KindRule(BaseModel):
    """One ``[[kind]]`` block — declares a file kind + how to detect it."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Stable kind id (used by [[view]] blocks).")
    match: KindMatch
    priority: int = Field(
        default=0,
        description=(
            "Higher priority wins when multiple kinds claim the same file. "
            "Built-in kinds use 0; domain plugins should use 100+."
        ),
    )
    container: ContainerSpec | None = Field(
        default=None,
        description="Folder-like behavior for files of this kind; see ContainerSpec.",
    )
    binary: bool = Field(
        default=False,
        description=(
            "Claim files whose content is binary, by path alone: the rule is asked only "
            "about a served file the server has already found to be binary, where it "
            "would otherwise be the ``binary`` kind, and only path predicates (``ext``, "
            "``exts``, ``basename``, ``folder_marker``, ``path_glob``) may match. A rule "
            "without it is never asked about a binary file."
        ),
    )


# The predicates that read a file's content. A ``binary`` rule may not use them, since
# the content they would read is not text.
CONTENT_MATCH_FIELDS: tuple[str, ...] = (
    "adapter",
    "frontmatter_has_key",
    "frontmatter_schema_prefix",
    "json_has_key",
    "json_value_prefix",
    "yaml_has_key",
    "yaml_value_prefix",
)


class ViewSpec(BaseModel):
    """One ``[[view]]`` block — binds a view to a kind."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(..., description="Matches a [[kind]].id from this or any plugin.")
    id: str = Field(..., description="View id, unique within a kind.")
    label: str = Field(..., description="Human label for the tab strip.")
    key: str | None = Field(
        default=None,
        description=(
            "Optional one-letter key for the view's tab, stored lowercase. It may not be "
            "a key the shell reserves in every context (metabrowser.keymap); uniqueness "
            "within a kind is checked on the merged view list, where the first view keeps "
            "a contested letter."
        ),
    )
    default: bool = Field(default=False, description="Show as the default view for this kind.")
    container_class: str = Field(
        default="content-body",
        description=(
            "CSS class applied to the view's outer <div>. Defaults to "
            "``content-body`` (the standard padding/scroll container). "
            "Markdown views typically use ``md-body`` for the prose styling."
        ),
    )
    printable: bool = Field(
        default=False,
        description="Whether the view has a complete print projection.",
    )
    print_profile: Literal["document", "source", "table", "tree", "plain"] = Field(
        default="plain",
        description="Print profile the shell and KPress adapter should apply.",
    )
    render_runtime: Literal["kpress", "client", "server", "plugin"] | None = Field(
        default=None,
        description="Descriptive runtime for the view renderer; JS registration still dispatches.",
    )
    offer: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z_][\w.]*:[A-Za-z_]\w*$",
        description=(
            "``module:function`` predicate that returns whether to offer the view. For "
            "the ``folder`` kind it receives the folder's path; it runs for every folder "
            "page, off the event loop, so it reads no more than a few directory entries, "
            "and an offered view with ``default = true`` is then the folder's only "
            "default. For a kind served as text it receives the file's leading logical "
            "bytes (at most ``CONTENT_PREDICATE_MAX_BYTES`` + 1) and its logical "
            "extension, and runs for every response that lists a text file's views, so "
            "it decides from those bytes alone; an image, binary, JSONL, or container "
            "entry's kind reads no bytes for it and never offers the view. Python "
            "plugins only: an operator directory's plugin never offers the view."
        ),
    )

    @field_validator("key")
    @classmethod
    def _key_is_a_free_letter(cls, key: str | None) -> str | None:
        if key is None:
            return None
        error = view_key_error(key)
        if error is not None:
            raise ValueError(error)
        return key.lower()


def view_entry(view: ViewSpec) -> dict[str, Any]:
    """Return the entry a file envelope's ``views`` list carries for *view*.

    ``key`` is present only when the view declares one.
    """
    return {
        "id": view.id,
        "label": view.label,
        **({"key": view.key} if view.key is not None else {}),
        "default": view.default,
        "container_class": view.container_class,
        "printable": view.printable,
        "print_profile": view.print_profile,
        "render_runtime": view.render_runtime,
    }


def merge_views(
    builtin: Iterable[Mapping[str, Any]], plugin: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Merge one kind's built-in registry entries with its manifest view entries.

    Plugin views are appended after built-in views; an exact id collision means
    the plugin entry overrides the earlier one in place (last write wins; the
    plugin author intentionally chose to register an existing id). The order in
    which they appear in the tab strip is built-ins first, then plugin order.
    The server and ``metab --doctor`` both merge through here, so the doctor
    checks the list the server serves.
    """
    out = [dict(view) for view in builtin]
    position = {view["id"]: index for index, view in enumerate(out)}
    for view in plugin:
        index = position.get(view["id"])
        if index is None:
            position[view["id"]] = len(out)
            out.append(dict(view))
        else:
            out[index] = dict(view)
    return out


class DataHookSpec(BaseModel):
    """One ``[[data_hook]]`` block — declares a Python sidekick handler."""

    model_config = ConfigDict(extra="forbid")

    route: str = Field(
        ...,
        description=("Route segment under /api/plugin/<plugin>/<route>. Must not contain slashes."),
    )
    sidekick: str = Field(
        ...,
        description=(
            "Python callable in ``module.path:callable`` form, e.g. "
            "``my_plugin.sidekick:viz_model_handler``. Imported once at startup."
        ),
    )
    methods: list[Literal["GET", "POST"]] = Field(
        default_factory=lambda: ["GET"],
        description="HTTP methods to mount the handler under.",
    )


class TableSourceSpec(BaseModel):
    """One ``[[table_source]]`` block — the adapter that serves a kind as tables.

    The built-in ``table`` plugin owns the routes; this declares which Python adapter
    answers them for files of one of this plugin's own kinds
    (:mod:`metabrowser.table_source`). Like a data hook, it runs only from a built-in or
    an installed distribution.
    """

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(..., description="A [[kind]].id this plugin declares, or folder.")
    adapter: str = Field(
        ...,
        description=(
            "Python callable in ``module.path:callable`` form that takes a TableHandle and "
            "returns a TableSource. Recorded as text and imported on first use."
        ),
    )
    offer: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z_][\w.]*:[A-Za-z_]\w*$",
        description="For folder tables, a bounded predicate receiving the directory path.",
    )


# The plugin that owns the table routes; a plugin declaring a [[table_source]] requires it.
TABLE_PLUGIN = "table"


# ── Plugin manifest ────────────────────────────────────────────


class PluginInfo(BaseModel):
    """The ``[plugin]`` table — plugin metadata."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ...,
        description=(
            "Lowercase plugin name. Used as the URL path segment under "
            "/plugin-static/<name>/ and /api/plugin/<name>/."
        ),
        pattern=_PLUGIN_NAME.pattern,
    )
    display_name: str = Field(default="", description="Human-readable plugin name.")
    version: str = Field(default="0.0.0", description="Plugin version, semver-ish.")
    sdk_version: str = Field(
        default=_IMPLICIT_PLUGIN_SDK_VERSION,
        description=(
            "Metabrowser plugin SDK contract version this plugin targets. "
            "An omitted value targets the original SDK 0.1. The resolved value "
            "must equal the host's PLUGIN_SDK_VERSION; the host provides no "
            "compatibility path for older SDKs."
        ),
    )
    register_module: str | None = Field(
        alias="register",
        default=None,
        description=(
            "Dotted Python module imported once when the plugin is discovered, for "
            "registrations such as ``register_log_adapter``. Built-in and entry-point "
            "plugins only: an operator-directory plugin is JavaScript-only, so the "
            "field is ignored there with a warning. An import failure is a plugin "
            "load error."
        ),
        pattern=r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$",
    )
    extra_scripts: list[str] = Field(
        default_factory=list,
        description=(
            "Additional script files (relative to plugin dir, no slashes) "
            "the shell should emit <script> tags for, in order, BEFORE "
            "index.js. Use for plugins that ship multiple JS files where "
            "index.js depends on them being loaded first. Each entry is "
            "served from /plugin-static/<plugin>/<filename>."
        ),
    )
    extra_styles: list[str] = Field(
        default_factory=list,
        description=(
            "Additional CSS files (relative to plugin dir, no slashes) "
            "the shell should emit <link rel='stylesheet'> tags for, in "
            "order, in addition to the default styles.css. Each entry "
            "is served from /plugin-static/<plugin>/<filename>."
        ),
    )
    requires: list[str] = Field(
        default_factory=list,
        description=(
            "Names of the plugins whose exports this plugin's browser code loads with "
            "``metabrowser.plugins.load(name)``, and ``table`` for a plugin that declares a "
            "``[[table_source]]``, whose routes the table plugin serves. Discovery refuses this plugin when one "
            "is not discovered or was refused, or when the requirements form a cycle "
            "(:func:`metabrowser.plugin_loader.discovery.resolve_requirements`)."
        ),
    )

    python_requires: list[str] = Field(
        default_factory=list,
        description=(
            "The third-party Python distributions this plugin's Python code imports, by "
            "distribution name, such as ``pyyaml``, whether or not core imports them too. "
            "The package's ``pyproject.toml`` pins their versions: a built-in plugin's "
            "packages ship with Metabrowser. Declaring them says which packages a plugin "
            "would need if it were moved out of the package; ``devtools/check_plugin_deps.py`` "
            "holds every built-in plugin's list to its imports."
        ),
    )

    @field_validator("requires")
    @classmethod
    def _requires_names_plugins(cls, requires: list[str]) -> list[str]:
        for name in requires:
            if not _PLUGIN_NAME.fullmatch(name):
                raise ValueError(f"requires entry {name!r} is not a plugin name")
        if len(set(requires)) != len(requires):
            raise ValueError(f"requires lists a plugin more than once: {requires}")
        return requires

    @field_validator("python_requires")
    @classmethod
    def _python_requires_names_distributions(cls, names: list[str]) -> list[str]:
        for name in names:
            if not _DISTRIBUTION_NAME.fullmatch(name):
                raise ValueError(f"python_requires entry {name!r} is not a distribution name")
        normalized = [normalize_distribution(name) for name in names]
        if len(set(normalized)) != len(normalized):
            raise ValueError(f"python_requires lists a distribution more than once: {names}")
        return names


class PluginManifest(BaseModel):
    """The full ``manifest.toml`` schema."""

    model_config = ConfigDict(extra="forbid")

    plugin: PluginInfo
    kind: list[KindRule] = Field(default_factory=list, description="Kind detection rules.")
    view: list[ViewSpec] = Field(default_factory=list, description="View bindings.")
    data_hook: list[DataHookSpec] = Field(
        default_factory=list, description="Python sidekick HTTP handlers."
    )
    table_source: list[TableSourceSpec] = Field(
        default_factory=list, description="Table source adapters for this plugin's kinds."
    )

    def validate_consistency(self) -> list[str]:
        """Return a list of human-readable validation problems.

        Empty list means the manifest is internally consistent.
        Cross-plugin checks (kind-id collisions across plugins) live in the
        loader, not here.
        """
        problems: list[str] = []

        # An SDK break is enforced, not absorbed. Refusing the plugin here
        # names the required version so the author can update, instead of
        # letting it load and fail later against a surface that moved.
        if self.plugin.sdk_version != PLUGIN_SDK_VERSION:
            problems.append(
                f"plugin '{self.plugin.name}' targets browser SDK "
                f"{self.plugin.sdk_version!r}, but this Metabrowser provides "
                f"{PLUGIN_SDK_VERSION!r}; update the plugin for the current SDK "
                "and set sdk_version accordingly"
            )

        # A plugin that requires itself is the shortest cycle; discovery refuses longer
        # ones, which need every manifest to see.
        if self.plugin.name in self.plugin.requires:
            problems.append(f"plugin '{self.plugin.name}' requires itself")

        # A container kind's children hook must be one of this plugin's
        # declared data hooks — the capability is a contract, not a URL.
        hook_routes = {hook.route for hook in self.data_hook}
        for kr in self.kind:
            if kr.container is not None and kr.container.children not in hook_routes:
                problems.append(
                    f"kind '{kr.id}' declares container.children="
                    f"{kr.container.children!r} but no [[data_hook]] has that route"
                )

        # A table source serves one of this plugin's own kinds, once, through the table
        # plugin's routes, so the dependency is declared and discovery can check it.
        local_kinds = {kr.id for kr in self.kind}
        source_kinds: set[str] = set()
        for spec in self.table_source:
            if spec.kind == "folder" and spec.offer is None:
                problems.append("a folder table source requires an offer")
            elif spec.kind != "folder" and spec.offer is not None:
                problems.append("only a folder table source can declare an offer")
            if spec.kind not in local_kinds and spec.kind != "folder":
                problems.append(
                    f"table_source kind '{spec.kind}' is not a [[kind]] this plugin declares"
                )
            if spec.kind in source_kinds:
                problems.append(f"table_source kind '{spec.kind}' is declared more than once")
            source_kinds.add(spec.kind)
            if ":" not in spec.adapter:
                problems.append(
                    f"table_source '{spec.kind}' has malformed adapter "
                    f"'{spec.adapter}'; expected module.path:callable"
                )
        if self.table_source and TABLE_PLUGIN not in self.plugin.requires:
            problems.append(
                f"plugin '{self.plugin.name}' declares a [[table_source]] but does not "
                f"require '{TABLE_PLUGIN}', whose routes serve it"
            )

        for kr in self.kind:
            content = [f for f in CONTENT_MATCH_FIELDS if getattr(kr.match, f) is not None]
            if kr.binary and content:
                problems.append(
                    f"kind '{kr.id}' claims binary files but matches on content "
                    f"({', '.join(content)}); a binary rule matches by path only"
                )
            if kr.binary and kr.match.magic is not None:
                problems.append(
                    f"kind '{kr.id}' sets binary with match.magic; a magic rule already "
                    "matches only binary files, by their bytes"
                )
            if kr.binary and kr.container is not None:
                problems.append(f"kind '{kr.id}' claims binary files and cannot be a container")

        # Each kind needs a non-empty match predicate.
        for kr in self.kind:
            if kr.match.is_empty():
                problems.append(
                    f"kind '{kr.id}' has an empty match predicate; "
                    "set at least one of ext/basename/frontmatter_has_key/etc."
                )
            # ext + exts are mutually exclusive — set one or the other.
            if kr.match.ext is not None and kr.match.exts is not None:
                problems.append(f"kind '{kr.id}' sets both match.ext and match.exts; pick one")
            # exts entries must be non-empty and start with a dot, mirroring
            # the single-ext shape so the classifier can compare ctx.ext directly.
            if kr.match.exts is not None:
                if len(kr.match.exts) == 0:
                    problems.append(
                        f"kind '{kr.id}' has match.exts = []; must contain at least one entry"
                    )
                for e in kr.match.exts:
                    if not e.startswith("."):
                        problems.append(
                            f"kind '{kr.id}' match.exts entry {e!r} must be a string "
                            "starting with '.'"
                        )
            if kr.match.magic is not None:
                magic = kr.match.magic
                if magic.offset + len(magic.expected) > MAGIC_MAX_END:
                    problems.append(
                        f"kind '{kr.id}' match.magic ends past byte {MAGIC_MAX_END}, "
                        "the sniff prefix a classification site holds"
                    )
                beside = [
                    name
                    for name in type(kr.match).model_fields
                    if name not in {"magic", "ext", "exts"} and getattr(kr.match, name) is not None
                ]
                if beside:
                    problems.append(
                        f"kind '{kr.id}' sets match.magic with {', '.join(beside)}; a magic "
                        "rule takes only ext or exts"
                    )
            # yaml_value_prefix is only meaningful paired with yaml_has_key
            # (mirrors the json pair).
            if kr.match.yaml_value_prefix is not None and kr.match.yaml_has_key is None:
                problems.append(
                    f"kind '{kr.id}' sets match.yaml_value_prefix without match.yaml_has_key; "
                    "set both, or neither"
                )

        # Every [[view]].kind must reference a [[kind]].id from this plugin
        # OR a kind shipped by a different plugin (the loader checks the
        # cross-plugin case; here we just allow unresolved references).
        local_kind_ids = {kr.id for kr in self.kind}
        for view in self.view:
            if not view.kind:
                problems.append(f"view '{view.id}' has empty kind field")

        # View ids should be unique within a kind.
        seen: dict[tuple[str, str], int] = {}
        for view in self.view:
            key = (view.kind, view.id)
            seen[key] = seen.get(key, 0) + 1
        for (kind, vid), count in seen.items():
            if count > 1:
                problems.append(f"view '{vid}' appears {count} times under kind '{kind}'")

        # At most one default per kind.
        defaults_per_kind: dict[str, list[str]] = {}
        for view in self.view:
            if view.default:
                defaults_per_kind.setdefault(view.kind, []).append(view.id)
        for kind, ids in defaults_per_kind.items():
            if len(ids) > 1:
                problems.append(
                    f"kind '{kind}' has multiple default views: {ids}; only one allowed"
                )

        # Data-hook routes must be unique within a plugin; Starlette resolves
        # duplicate paths in registration order, which would silently make
        # every later hook for the same route unreachable.
        hook_route_counts: dict[str, int] = {}
        for dh in self.data_hook:
            hook_route_counts[dh.route] = hook_route_counts.get(dh.route, 0) + 1
            if ":" not in dh.sidekick:
                problems.append(
                    f"data_hook '{dh.route}' has malformed sidekick "
                    f"'{dh.sidekick}'; expected module.path:callable"
                )
            if "/" in dh.route:
                problems.append(
                    f"data_hook route '{dh.route}' contains '/'; routes are single segments"
                )
        for route, count in hook_route_counts.items():
            if count > 1:
                problems.append(
                    f"data_hook route '{route}' appears {count} times; routes must be unique"
                )

        # extra_scripts / extra_styles entries must be plain filenames
        # (no path separators, no traversal). The /plugin-static/ route
        # already guards against traversal at request time, but
        # rejecting bad entries at manifest-load gives operators a
        # clear error instead of a silent 404.
        for entry in self.plugin.extra_scripts:
            if "/" in entry or ".." in entry or entry.startswith("."):
                problems.append(
                    f"plugin.extra_scripts entry '{entry}' must be a plain filename "
                    "(no slashes, no '..', no leading dot)"
                )
        for entry in self.plugin.extra_styles:
            if "/" in entry or ".." in entry or entry.startswith("."):
                problems.append(
                    f"plugin.extra_styles entry '{entry}' must be a plain filename "
                    "(no slashes, no '..', no leading dot)"
                )

        # Local kinds referenced by views — emit info-level if a view
        # points at a kind that's neither local nor obviously prefixed
        # by another plugin namespace. We can't fully validate without
        # the loader's cross-plugin view, so leave this to the loader.
        unresolved_local = {v.kind for v in self.view if v.kind not in local_kind_ids}
        # Stash on a private attribute the loader reads.
        object.__setattr__(self, "_unresolved_kinds", unresolved_local)

        return problems


def load_manifest(path: Path) -> PluginManifest:
    """Read and validate a plugin's ``manifest.toml``.

    Raises FileNotFoundError if path doesn't exist; pydantic ValidationError
    on schema problems; ValueError on consistency problems.
    """
    with path.open("rb") as f:
        data = tomllib.load(f)
    manifest = PluginManifest.model_validate(data)
    problems = manifest.validate_consistency()
    if problems:
        raise ValueError(
            f"Plugin manifest {path} has {len(problems)} problem(s):\n  - "
            + "\n  - ".join(problems)
        )
    return manifest
