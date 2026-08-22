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

import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
PLUGIN_SDK_VERSION = "0.3"

# Metabrowser 0.4.0 allowed manifests to omit sdk_version. Such a manifest
# targets the only SDK that existed under that contract. Keep this value pinned
# when PLUGIN_SDK_VERSION changes so omission fails the ordinary mismatch gate.
_IMPLICIT_PLUGIN_SDK_VERSION = "0.1"

# ── Match predicate ────────────────────────────────────────────


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

    def is_empty(self) -> bool:
        """Return True if no predicate fields are set."""
        return all(getattr(self, f) is None for f in type(self).model_fields)


# ── Kind, view, data_hook ──────────────────────────────────────


class ContainerSpec(BaseModel):
    """The ``container`` table on a ``[[kind]]`` — folder-like behavior.

    A container kind's files play both nav-tree roles from
    ``docs/project/architecture/arch-nav-containers.md``: item-like
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


class ViewSpec(BaseModel):
    """One ``[[view]]`` block — binds a view to a kind."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(..., description="Matches a [[kind]].id from this or any plugin.")
    id: str = Field(..., description="View id, unique within a kind.")
    label: str = Field(..., description="Human label for the tab strip.")
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
        pattern=r"^[a-z][a-z0-9_-]*$",
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


class PluginManifest(BaseModel):
    """The full ``manifest.toml`` schema."""

    model_config = ConfigDict(extra="forbid")

    plugin: PluginInfo
    kind: list[KindRule] = Field(default_factory=list, description="Kind detection rules.")
    view: list[ViewSpec] = Field(default_factory=list, description="View bindings.")
    data_hook: list[DataHookSpec] = Field(
        default_factory=list, description="Python sidekick HTTP handlers."
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

        # A container kind's children hook must be one of this plugin's
        # declared data hooks — the capability is a contract, not a URL.
        hook_routes = {hook.route for hook in self.data_hook}
        for kr in self.kind:
            if kr.container is not None and kr.container.children not in hook_routes:
                problems.append(
                    f"kind '{kr.id}' declares container.children="
                    f"{kr.container.children!r} but no [[data_hook]] has that route"
                )

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
