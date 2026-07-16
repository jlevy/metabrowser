"""Verify the standalone repository's package-resolution policy."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NPM_MIN_RELEASE_AGE_DAYS = "14"
NODE_VERSION = "24.18.0"
NODE_RANGE = ">=24.18.0 <25"
NPM_RANGE = ">=11.10.0 <12"
CHECKOUT_SHA = "9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"
SETUP_UV_SHA = "fac544c07dec837d0ccb6301d7b5580bf5edae39"
SETUP_NODE_SHA = "48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e"
UV_VERSION = "0.11.26"
UV_LINUX_CHECKSUM = "6426a73c3837e6e2483ee344cbc00f36394d179afcba6183cb77437e67db4af0"
BUILD_PINS = ["hatchling==1.30.1", "uv-dynamic-versioning==0.14.0"]
CLI_SCRIPTS = {
    "metab": "metabrowser.cli.serve:main",
    "metabrowser": "metabrowser.cli.serve:main",
}
RUNTIME_REQUIREMENTS = [
    "cachetools>=7.1.4",
    "frontmatter-format>=0.3.0",
    "funlog>=0.2.1",
    "json5>=0.15.0",
    "jsonschema>=4.26.0",
    "kpress==0.2.2",
    "pathspec>=1.1.1",
    "prettyfmt>=0.4.1",
    "psutil>=7.2.2",
    "pydantic>=2.13.4",
    "python-dotenv>=1.2.2",
    "pyyaml>=6.0.3",
    "ruamel.yaml>=0.19.1",
    "starlette>=1.3.1",
    "strif>=3.1.0",
    "typer>=0.26.8",
    "uvicorn>=0.49.0",
    "watchfiles>=1.2.0",
]
PYTHON_TOOL_FLOORS = {
    "basedpyright>=1.39.9",
    "codespell>=2.4.2",
    "pytest>=9.1.1",
    "pytest-timeout>=2.4.0",
    "ruff>=0.15.20",
}
GLOBAL_BASEDPYRIGHT_RATCHET_RULES = {
    "reportMissingParameterType",
    "reportPrivateUsage",
    "reportUnknownArgumentType",
    "reportUnknownLambdaType",
    "reportUnknownMemberType",
    "reportUnknownParameterType",
    "reportUnknownVariableType",
    "reportUnusedClass",
    "reportUnusedFunction",
    "reportUnusedImport",
}
BASEDPYRIGHT_EXECUTION_ENVIRONMENTS = [
    {
        "root": "src",
        "reportPrivateUsage": False,
        "reportUnknownArgumentType": False,
        "reportUnknownMemberType": False,
        "reportUnknownVariableType": False,
        "reportUnusedFunction": False,
    },
    {
        "root": "tests",
        "extraPaths": ["."],
        "reportPrivateUsage": False,
        "reportUnknownArgumentType": False,
        "reportUnknownLambdaType": False,
        "reportUnknownMemberType": False,
        "reportUnknownParameterType": False,
        "reportUnknownVariableType": False,
        "reportMissingParameterType": False,
    },
]
LEGACY_JAVASCRIPT_FILES = [
    "src/metabrowser/static/app.js",
    "src/metabrowser/static/charts.js",
    "src/metabrowser/static/icons.js",
    "src/metabrowser/static/perf.js",
    "src/metabrowser/static/plugin_sdk.js",
    "src/metabrowser/builtin_plugins/agent_log/index.js",
    "src/metabrowser/builtin_plugins/markdown/index.js",
    "src/metabrowser/builtin_plugins/structured/index.js",
    "src/metabrowser/builtin_plugins/structured/preview.js",
    "src/metabrowser/builtin_plugins/structured/tree.js",
]
BIOME_OVERRIDES = [
    {
        "includes": ["src/metabrowser/static/styles.css"],
        "linter": {"rules": {"style": {"noDescendingSpecificity": "off"}}},
    },
    {
        "includes": [
            "src/metabrowser/static/app.js",
            "src/metabrowser/static/charts.js",
            "src/metabrowser/static/perf.js",
            "src/metabrowser/builtin_plugins/structured/preview.js",
            "src/metabrowser/builtin_plugins/structured/tree.js",
        ],
        "linter": {"rules": {"correctness": {"noInnerDeclarations": "off"}}},
    },
]
NPM_TOOL_PINS = {
    "@biomejs/biome": "2.5.2",
    "lefthook": "2.1.9",
    "typescript": "6.0.3",
}
FLOWMARK_VERSION = "0.3.2"
FLOWMARK_EXCEPTION = "2026-07-16T00:00:00Z"
TBD_VERSION = "0.4.0"
UV_REPOSITORY_SUBCOMMANDS = "add|build|lock|publish|run|sync"


def _verify_repository_uv_commands(source: str, text: str) -> None:
    """Reject repository uv commands that do not select ``uv.toml``."""
    if re.search(rf"\buv\s+(?:{UV_REPOSITORY_SUBCOMMANDS})\b", text):
        raise RuntimeError(f"{source} uses a repository uv command without --config-file uv.toml")


def _verify_documented_uv_commands(source: str, text: str) -> None:
    """Reject documentation commands that bypass the repository uv policy."""
    if re.search(r"\buv(?:\s+--config-file\s+uv\.toml)?\s+run(?! --frozen)(?=\s)", text):
        raise RuntimeError(f"{source} documents a non-frozen uv run command")
    _verify_repository_uv_commands(source, text)


def verify_repo_package_policy(root: Path = ROOT) -> None:
    """Raise when package or tool configuration bypasses repository policy."""
    npmrc = (root / ".npmrc").read_text(encoding="utf-8")
    required_npmrc = {
        "engine-strict=true",
        "ignore-scripts=true",
        f"min-release-age={NPM_MIN_RELEASE_AGE_DAYS}",
        "package-lock=true",
        "save-exact=true",
    }
    missing = sorted(line for line in required_npmrc if line not in npmrc.splitlines())
    if missing:
        raise RuntimeError(f".npmrc is missing required settings: {missing}")

    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]
    if dependencies != RUNTIME_REQUIREMENTS:
        missing = sorted(set(RUNTIME_REQUIREMENTS) - set(dependencies))
        unexpected = sorted(set(dependencies) - set(RUNTIME_REQUIREMENTS))
        raise RuntimeError(
            "runtime requirements must preserve the reviewed version constraints; "
            f"missing={missing}, unexpected={unexpected}"
        )
    if pyproject["project"].get("scripts") != CLI_SCRIPTS:
        raise RuntimeError(
            "project scripts must expose metab with the metabrowser compatibility alias"
        )
    if pyproject["dependency-groups"].get("build") != BUILD_PINS:
        raise RuntimeError("the build dependency group must contain the exact backend pins")
    if pyproject["build-system"].get("requires") != BUILD_PINS:
        raise RuntimeError("the isolated build system must contain the exact backend pins")
    if not PYTHON_TOOL_FLOORS.issubset(pyproject["dependency-groups"].get("dev", [])):
        raise RuntimeError("the development group must preserve the reviewed Python tool floors")
    basedpyright = pyproject["tool"]["basedpyright"]
    if basedpyright.get("typeCheckingMode") != "strict":
        raise RuntimeError("BasedPyright must retain the global strict type-checking floor")
    broad_type_exceptions = sorted(
        rule for rule in GLOBAL_BASEDPYRIGHT_RATCHET_RULES if basedpyright.get(rule) is False
    )
    if broad_type_exceptions:
        raise RuntimeError(
            f"BasedPyright legacy exceptions must not be global: {broad_type_exceptions}"
        )
    if basedpyright.get("executionEnvironments") != BASEDPYRIGHT_EXECUTION_ENVIRONMENTS:
        raise RuntimeError("BasedPyright legacy exceptions must match the reviewed scoped baseline")

    tsconfig = json.loads((root / "tsconfig.json").read_text(encoding="utf-8"))
    legacy_tsconfig = json.loads((root / "tsconfig.legacy.json").read_text(encoding="utf-8"))
    if tsconfig.get("compilerOptions", {}).get("noImplicitAny") is not True:
        raise RuntimeError("the primary TypeScript checkJs project must reject implicit any")
    if legacy_tsconfig.get("compilerOptions") != {"noImplicitAny": False}:
        raise RuntimeError("the legacy TypeScript project may relax only noImplicitAny")
    if tsconfig.get("exclude") != LEGACY_JAVASCRIPT_FILES:
        raise RuntimeError("the strict TypeScript exclusion list must match the legacy ratchet")
    expected_legacy_files = ["src/metabrowser/static/types.d.ts", *LEGACY_JAVASCRIPT_FILES]
    if legacy_tsconfig.get("files") != expected_legacy_files:
        raise RuntimeError("the legacy TypeScript allowlist must match the reviewed ratchet")

    biome = json.loads((root / "biome.json").read_text(encoding="utf-8"))
    global_biome_rules = biome.get("linter", {}).get("rules", {})
    if global_biome_rules.get("correctness", {}).get("noInnerDeclarations") == "off" or (
        global_biome_rules.get("style", {}).get("noDescendingSpecificity") == "off"
    ):
        raise RuntimeError("Biome legacy rule exceptions must not be global")
    if biome.get("overrides") != BIOME_OVERRIDES:
        raise RuntimeError("Biome legacy exceptions must match the reviewed file-scoped baseline")

    uv_toml = tomllib.loads((root / "uv.toml").read_text(encoding="utf-8"))
    if uv_toml.get("required-version") != f">={UV_VERSION}":
        raise RuntimeError(f"uv.toml must require uv >={UV_VERSION}")
    if uv_toml.get("exclude-newer") != "14 days":
        raise RuntimeError("uv.toml must preserve the 14-day cool-off")
    expected_exceptions = {
        "flowmark-rs": FLOWMARK_EXCEPTION,
        "kpress": "2026-07-16T00:00:00Z",
    }
    if uv_toml.get("exclude-newer-package") != expected_exceptions:
        raise RuntimeError("uv.toml must contain only the audited package exceptions")

    lock_path = root / "uv.lock"
    if lock_path.exists():
        lock = tomllib.loads(lock_path.read_text(encoding="utf-8"))
        kpress = [package for package in lock.get("package", []) if package.get("name") == "kpress"]
        if len(kpress) != 1 or kpress[0].get("version") != "0.2.2":
            raise RuntimeError("uv.lock must contain exactly kpress==0.2.2")
        if kpress[0].get("source") != {"registry": "https://pypi.org/simple"}:
            raise RuntimeError("KPress must resolve from the PyPI registry")
        if lock.get("options", {}).get("exclude-newer-package") != expected_exceptions:
            raise RuntimeError("uv.lock contains an unreviewed package-age exception")

    publish_workflow = (root / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    if "types: [published]" not in publish_workflow or "workflow_dispatch" in publish_workflow:
        raise RuntimeError("publishing must be triggered only by a published GitHub release")
    if "enable-cache: false" not in publish_workflow:
        raise RuntimeError("publishing must explicitly disable the uv cache")
    if "enable-cache: true" in publish_workflow or re.search(
        r'^\s*cache:\s*["\']?npm', publish_workflow, re.MULTILINE
    ):
        raise RuntimeError("publishing must not restore mutable dependency caches")

    package_json = root / "package.json"
    package_lock = root / "package-lock.json"
    if not package_json.is_file() or not package_lock.is_file():
        raise RuntimeError("the exact npm toolchain requires package.json and package-lock.json")

    package_data = json.loads(package_json.read_text(encoding="utf-8"))
    if package_data.get("private") is not True:
        raise RuntimeError("the npm development-tool package must remain private")
    if package_data.get("engines") != {"node": NODE_RANGE, "npm": NPM_RANGE}:
        raise RuntimeError("package.json must require the reviewed Node and npm ranges")
    for relative in (".node-version", ".nvmrc"):
        path = root / relative
        if not path.is_file() or path.read_text(encoding="utf-8").strip() != NODE_VERSION:
            raise RuntimeError(f"{relative} must pin Node {NODE_VERSION}")
    if package_data.get("devDependencies") != NPM_TOOL_PINS:
        raise RuntimeError("package.json must contain only the reviewed exact npm tool pins")

    lock_data = json.loads(package_lock.read_text(encoding="utf-8"))
    lock_packages = lock_data.get("packages", {})
    if lock_packages.get("", {}).get("devDependencies") != NPM_TOOL_PINS:
        raise RuntimeError("package-lock.json root pins do not match package.json")
    if lock_packages.get("", {}).get("engines") != package_data["engines"]:
        raise RuntimeError("package-lock.json root engines do not match package.json")
    for package, version in NPM_TOOL_PINS.items():
        locked = lock_packages.get(f"node_modules/{package}", {})
        if locked.get("version") != version:
            raise RuntimeError(f"package-lock.json must contain exact {package}@{version}")
        if not str(locked.get("resolved", "")).startswith("https://registry.npmjs.org/"):
            raise RuntimeError(f"{package} must resolve from the npm registry")
        if not str(locked.get("integrity", "")).startswith("sha512-"):
            raise RuntimeError(f"{package} must have a sha512 lockfile integrity hash")
    for package_path, locked in lock_packages.items():
        if not package_path:
            continue
        if not str(locked.get("resolved", "")).startswith("https://registry.npmjs.org/"):
            raise RuntimeError(f"{package_path} must resolve from the npm registry")
        if not str(locked.get("integrity", "")).startswith("sha512-"):
            raise RuntimeError(f"{package_path} must have a sha512 lockfile integrity hash")

    tooling_paths = [
        root / "Makefile",
        root / ".github/workflows/ci.yml",
        root / ".github/workflows/publish.yml",
        root / "lefthook.yml",
        root / "devtools/biome.py",
        root / "devtools/tsc_check.py",
    ]
    tooling_text = "\n".join(path.read_text(encoding="utf-8") for path in tooling_paths)
    makefile_text = (root / "Makefile").read_text(encoding="utf-8")
    if "UV := uv --config-file $(CURDIR)/uv.toml" not in makefile_text:
        raise RuntimeError("Make targets must select the repository uv configuration")
    if "UVX := uvx --config-file $(CURDIR)/uv.toml" not in makefile_text:
        raise RuntimeError("Make targets must select the repository uvx configuration")
    if "UV_RUN := $(UV) run --frozen" not in makefile_text:
        raise RuntimeError("Make targets must use a frozen uv runner")
    ambient_npm_policy = (
        "NPM_CONFIG_BEFORE",
        "NPM_CONFIG_FROZEN_LOCKFILE",
        "NPM_CONFIG_MINIMUM_RELEASE_AGE",
    )
    missing_npm_unexports = [
        variable for variable in ambient_npm_policy if f"unexport {variable}" not in makefile_text
    ]
    if missing_npm_unexports:
        raise RuntimeError(
            f"Make targets must ignore conflicting ambient npm policy: {missing_npm_unexports}"
        )
    if re.search(r"^\tuvx?\s", makefile_text, re.MULTILINE):
        raise RuntimeError("Make recipes must not invoke bare uv or uvx")
    if (
        "default: install\n\t$(MAKE) SKIP_INSTALL=1 format\n"
        "\t$(MAKE) SKIP_INSTALL=1 lint\n\t$(MAKE) SKIP_INSTALL=1 test" not in makefile_text
    ):
        raise RuntimeError("the mutating default workflow must run format, lint, and test serially")
    if "format lint: | install" not in makefile_text or (
        "lint-check test audit build: | install" not in makefile_text
    ):
        raise RuntimeError("parallel quality gates must wait for the install target")
    lefthook_text = (root / "lefthook.yml").read_text(encoding="utf-8")
    if re.search(r"^\s*run:\s+uv\s+(?!--config-file uv\.toml\s)", lefthook_text, re.MULTILINE):
        raise RuntimeError("hooks must select the repository uv configuration")
    command_doc_paths = [
        root / "AGENTS.md",
        root / "README.md",
        *sorted((root / "docs").glob("*.md")),
    ]
    for path in command_doc_paths:
        _verify_documented_uv_commands(
            str(path.relative_to(root)), path.read_text(encoding="utf-8")
        )
    required_flowmark_controls = (
        f"FLOWMARK_VERSION := {FLOWMARK_VERSION}",
        f"FLOWMARK_EXCEPTION := {FLOWMARK_EXCEPTION}",
        "flowmark-rs@$(FLOWMARK_VERSION)",
    )
    if any(control not in makefile_text for control in required_flowmark_controls):
        raise RuntimeError("Flowmark tooling is missing its exact pin or reviewed exception")
    agents_text = (root / "AGENTS.md").read_text(encoding="utf-8")
    if f"flowmark-rs=={FLOWMARK_VERSION}" not in agents_text:
        raise RuntimeError("AGENTS.md must document the exact Flowmark tool pin")
    if tooling_text.count("npx --no-install") < 1 or tooling_text.count("npx_no_install") < 2:
        raise RuntimeError("npm tools must run from the lock with npx --no-install")
    if "npx --yes" in tooling_text or '"--package"' in tooling_text:
        raise RuntimeError("npm tools must never fetch packages during lint or type checking")
    if "npm ci" not in tooling_text:
        raise RuntimeError("CI and local setup must install the committed npm lock")
    required_audit_commands = (
        "npm audit --audit-level=moderate",
        "$(UV) --preview-features audit-command audit --frozen",
    )
    if any(command not in tooling_text for command in required_audit_commands):
        raise RuntimeError("the audit gate must inspect the locked npm and Python graphs")
    if "@latest" in tooling_text:
        raise RuntimeError("tooling must not use @latest")

    agent_tbd_paths = [
        root / ".agents/skills/tbd/SKILL.md",
        root / ".claude/skills/tbd/SKILL.md",
    ]
    for path in agent_tbd_paths:
        text = path.read_text(encoding="utf-8")
        if f"get-tbd@{TBD_VERSION}" not in text or "@latest" in text:
            raise RuntimeError(f"{path.relative_to(root)} must pin get-tbd@{TBD_VERSION}")
    agent_tbd_hook_paths = [
        root / ".codex/tbd-session.sh",
        root / ".codex/tbd-closing-reminder.sh",
        root / ".claude/scripts/tbd-session.sh",
        root / ".claude/hooks/tbd-closing-reminder.sh",
    ]
    for path in agent_tbd_hook_paths:
        text = path.read_text(encoding="utf-8")
        if "npx --yes" in text or "npx --package" in text:
            raise RuntimeError(f"{path.relative_to(root)} must not fetch tbd from a hook")
    for path in (root / ".codex/tbd-session.sh", root / ".claude/scripts/tbd-session.sh"):
        if f"npm install -g get-tbd@{TBD_VERSION}" not in path.read_text(encoding="utf-8"):
            raise RuntimeError(f"{path.relative_to(root)} must document the exact tbd install")

    workflow_paths = sorted((root / ".github" / "workflows").glob("*.yml"))
    workflow_text = "\n".join(path.read_text(encoding="utf-8") for path in workflow_paths)
    _verify_repository_uv_commands("GitHub Actions workflows", workflow_text)
    action_uses = re.findall(r"^\s*uses:\s+[^@\s]+@([^\s#]+)", workflow_text, re.MULTILINE)
    mutable_actions = [ref for ref in action_uses if re.fullmatch(r"[0-9a-f]{40}", ref) is None]
    if mutable_actions:
        raise RuntimeError(f"GitHub Actions must use full commit SHAs: {mutable_actions}")
    required_workflow_pins = [
        f"actions/checkout@{CHECKOUT_SHA}",
        f"astral-sh/setup-uv@{SETUP_UV_SHA}",
        f"actions/setup-node@{SETUP_NODE_SHA}",
        f'version: "{UV_VERSION}"',
        f'checksum: "{UV_LINUX_CHECKSUM}"',
    ]
    missing_workflow_pins = [
        value for value in required_workflow_pins if value not in workflow_text
    ]
    if missing_workflow_pins:
        raise RuntimeError(f"workflows are missing reviewed pins: {missing_workflow_pins}")
    node_versions = set(
        re.findall(r'^\s*node-version:\s*["\']?([^\s"\']+)', workflow_text, re.MULTILINE)
    )
    if node_versions != {NODE_VERSION}:
        raise RuntimeError(f"workflows must use only Node {NODE_VERSION}, got {node_versions}")
    checkout_count = workflow_text.count(f"actions/checkout@{CHECKOUT_SHA}")
    if workflow_text.count("persist-credentials: false") != checkout_count:
        raise RuntimeError("every checkout must disable persisted credentials")
    if workflow_text.count("fetch-depth: 0") != checkout_count:
        raise RuntimeError("every checkout must fetch tags for dynamic versioning")
    required_publish_controls = [
        "environment: pypi",
        "ref: ${{ github.event.release.tag_name }}",
        "run: make verify",
        "^v[0-9]+\\.[0-9]+\\.[0-9]+$",
        "metabrowser.__version__",
        "uv --config-file uv.toml publish --trusted-publishing always",
    ]
    missing_publish_controls = [
        value for value in required_publish_controls if value not in publish_workflow
    ]
    if missing_publish_controls:
        raise RuntimeError(f"publish workflow is missing controls: {missing_publish_controls}")


def main() -> int:
    verify_repo_package_policy()
    print("Package policy checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
