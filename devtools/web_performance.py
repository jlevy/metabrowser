"""Reusable validity and budget checks for browser performance loops.

The browser runtime and an application adapter produce one flat JSON record.
This module decides whether that record is admissible and whether an absolute
budget passed. It deliberately knows no Metabrowser DOM selectors or routes;
another web application can use it with its own TOML budget file.
"""

from __future__ import annotations

import math
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

BudgetPolicy = Literal["gate", "target"]
IssueKind = Literal["invalid", "budget"]
CONFIG_SCHEMA = "web-performance-budgets/v1"


@dataclass(frozen=True)
class MetricBudget:
    """One upper bound and whether it blocks acceptance."""

    metric: str
    category: str
    maximum: float
    policy: BudgetPolicy
    required: bool
    description: str


@dataclass(frozen=True)
class PerformanceRequirements:
    """Facts a browser record must establish before its numbers are usable."""

    profile_schema: str
    responsiveness_source: str
    vitals_source: str
    require_visible: bool
    require_interactions: bool
    minimum_interaction_inputs: int
    minimum_interaction_coverage_pct: float
    require_no_label_overflow: bool
    require_no_resource_overflow: bool
    required_observers: tuple[str, ...]
    required_fields: tuple[str, ...]
    minimum_runs_per_condition: int
    completion_field: str | None
    completion_values: tuple[str, ...]


@dataclass(frozen=True)
class PerformanceConfig:
    """Portable browser-run requirements plus application-selected budgets."""

    requirements: PerformanceRequirements
    budgets: tuple[MetricBudget, ...]


@dataclass(frozen=True)
class PerformanceIssue:
    """One reason a run is invalid or exceeds an absolute budget."""

    kind: IssueKind
    code: str
    message: str
    metric: str | None = None
    actual: float | None = None
    maximum: float | None = None
    policy: BudgetPolicy | None = None


def _table(raw: object, name: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{name} must be a TOML table")
    return cast("dict[str, Any]", raw)


def load_performance_config(path: Path) -> PerformanceConfig:
    """Load a reusable performance contract from TOML."""
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema") != CONFIG_SCHEMA:
        raise ValueError(f"schema must be {CONFIG_SCHEMA!r}")
    requirements_raw = _table(raw.get("requirements"), "requirements")
    observers_raw = requirements_raw.get("required_observers", [])
    if not isinstance(observers_raw, list):
        raise ValueError("requirements.required_observers must be an array of strings")
    observer_values = cast("list[object]", observers_raw)
    if not all(isinstance(value, str) for value in observer_values):
        raise ValueError("requirements.required_observers must be an array of strings")
    required_observers = cast("list[str]", observer_values)
    required_fields_raw = requirements_raw.get("required_fields", [])
    if not isinstance(required_fields_raw, list):
        raise ValueError("requirements.required_fields must be an array of strings")
    required_field_objects = cast("list[object]", required_fields_raw)
    if not all(isinstance(value, str) and value for value in required_field_objects):
        raise ValueError("requirements.required_fields must be an array of non-empty strings")
    required_fields = cast("list[str]", required_field_objects)
    completion_values_raw = requirements_raw.get("completion_values", [])
    if not isinstance(completion_values_raw, list):
        raise ValueError("requirements.completion_values must be an array of strings")
    completion_value_objects = cast("list[object]", completion_values_raw)
    if not all(isinstance(value, str) for value in completion_value_objects):
        raise ValueError("requirements.completion_values must be an array of strings")
    completion_values = cast("list[str]", completion_value_objects)
    profile_schema = requirements_raw.get("profile_schema")
    responsiveness_source = requirements_raw.get("responsiveness_source")
    vitals_source = requirements_raw.get("vitals_source")
    if not isinstance(profile_schema, str) or not profile_schema:
        raise ValueError("requirements.profile_schema must be a non-empty string")
    if not isinstance(responsiveness_source, str) or not responsiveness_source:
        raise ValueError("requirements.responsiveness_source must be a non-empty string")
    if not isinstance(vitals_source, str) or not vitals_source:
        raise ValueError("requirements.vitals_source must be a non-empty string")
    minimum_runs = requirements_raw.get("minimum_runs_per_condition", 1)
    if not isinstance(minimum_runs, int) or isinstance(minimum_runs, bool) or minimum_runs < 1:
        raise ValueError("requirements.minimum_runs_per_condition must be a positive integer")
    minimum_interaction_inputs = requirements_raw.get("minimum_interaction_inputs", 1)
    if (
        not isinstance(minimum_interaction_inputs, int)
        or isinstance(minimum_interaction_inputs, bool)
        or minimum_interaction_inputs < 1
    ):
        raise ValueError("requirements.minimum_interaction_inputs must be a positive integer")
    minimum_interaction_coverage_pct = requirements_raw.get("minimum_interaction_coverage_pct", 0)
    if (
        not isinstance(minimum_interaction_coverage_pct, (int, float))
        or isinstance(minimum_interaction_coverage_pct, bool)
        or not math.isfinite(float(minimum_interaction_coverage_pct))
        or not 0 <= float(minimum_interaction_coverage_pct) <= 100
    ):
        raise ValueError("requirements.minimum_interaction_coverage_pct must be between 0 and 100")
    completion_field_raw = requirements_raw.get("completion_field")
    if completion_field_raw is not None and (
        not isinstance(completion_field_raw, str) or not completion_field_raw
    ):
        raise ValueError("requirements.completion_field must be a non-empty string")
    if completion_field_raw is not None and not completion_values:
        raise ValueError(
            "requirements.completion_values must not be empty when completion_field is set"
        )
    requirements = PerformanceRequirements(
        profile_schema=profile_schema,
        responsiveness_source=responsiveness_source,
        vitals_source=vitals_source,
        require_visible=bool(requirements_raw.get("require_visible", True)),
        require_interactions=bool(requirements_raw.get("require_interactions", True)),
        minimum_interaction_inputs=minimum_interaction_inputs,
        minimum_interaction_coverage_pct=float(minimum_interaction_coverage_pct),
        require_no_label_overflow=bool(requirements_raw.get("require_no_label_overflow", True)),
        require_no_resource_overflow=bool(
            requirements_raw.get("require_no_resource_overflow", True)
        ),
        required_observers=tuple(required_observers),
        required_fields=tuple(required_fields),
        minimum_runs_per_condition=minimum_runs,
        completion_field=completion_field_raw,
        completion_values=tuple(completion_values),
    )

    budgets_raw = _table(raw.get("metrics"), "metrics")
    budgets: list[MetricBudget] = []
    for metric, value in budgets_raw.items():
        item = _table(value, f"metrics.{metric}")
        policy = item.get("policy", "target")
        if policy not in ("gate", "target"):
            raise ValueError(f"metrics.{metric}.policy must be 'gate' or 'target'")
        maximum = item.get("maximum")
        if (
            not isinstance(maximum, (int, float))
            or isinstance(maximum, bool)
            or not math.isfinite(float(maximum))
        ):
            raise ValueError(f"metrics.{metric}.maximum must be a finite number")
        budgets.append(
            MetricBudget(
                metric=metric,
                category=str(item.get("category", "application")),
                maximum=float(maximum),
                policy=policy,
                required=bool(item.get("required", False)),
                description=str(item.get("description", "")),
            )
        )
    return PerformanceConfig(requirements=requirements, budgets=tuple(budgets))


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def validity_issues(payload: dict[str, Any], config: PerformanceConfig) -> list[PerformanceIssue]:
    """Reject measurements whose provenance cannot support a comparison."""
    required = config.requirements
    issues: list[PerformanceIssue] = []
    missing_fields = [
        field
        for field in required.required_fields
        if field not in payload or payload[field] is None or payload[field] == ""
    ]
    if missing_fields:
        issues.append(
            PerformanceIssue(
                kind="invalid",
                code="provenance-missing",
                message=f"required run provenance is missing: {missing_fields}",
            )
        )
    if payload.get("performance_profile_schema") != required.profile_schema:
        issues.append(
            PerformanceIssue(
                kind="invalid",
                code="profile-schema",
                message=(
                    "navigation-time performance profile is missing or has the wrong schema "
                    f"(expected {required.profile_schema!r})"
                ),
            )
        )
    if payload.get("responsiveness_source") != required.responsiveness_source:
        issues.append(
            PerformanceIssue(
                kind="invalid",
                code="late-profiler",
                message="responsiveness was not captured by the navigation-time profiler",
            )
        )
    if payload.get("vitals_source") != required.vitals_source:
        issues.append(
            PerformanceIssue(
                kind="invalid",
                code="late-vitals",
                message="paint and layout stability were not captured by the navigation-time profiler",
            )
        )
    if required.require_visible and (
        payload.get("measurement_valid") is not True
        or payload.get("visibility_state") != "visible"
        or payload.get("ever_hidden") is not False
    ):
        issues.append(
            PerformanceIssue(
                kind="invalid",
                code="not-visible-throughout",
                message="the browser tab was not proven visible for the complete measurement window",
            )
        )
    unsupported_raw = payload.get("unsupported")
    unsupported_values = (
        cast("list[object]", unsupported_raw) if isinstance(unsupported_raw, list) else []
    )
    unsupported = {value for value in unsupported_values if isinstance(value, str)}
    missing_observers = sorted(set(required.required_observers) & unsupported)
    if missing_observers:
        issues.append(
            PerformanceIssue(
                kind="invalid",
                code="observer-unsupported",
                message=f"required PerformanceObserver signals are unavailable: {missing_observers}",
            )
        )
    if required.require_interactions:
        interaction_inputs = _number(payload.get("interaction_inputs"))
        if interaction_inputs is None or interaction_inputs < required.minimum_interaction_inputs:
            issues.append(
                PerformanceIssue(
                    kind="invalid",
                    code="insufficient-interactions",
                    message=(
                        "trusted input did not cover enough of the run: "
                        f"need at least {required.minimum_interaction_inputs} inputs"
                    ),
                )
            )
        interaction_coverage = _number(payload.get("interaction_input_coverage_pct"))
        if (
            interaction_coverage is None
            or interaction_coverage < required.minimum_interaction_coverage_pct
        ):
            issues.append(
                PerformanceIssue(
                    kind="invalid",
                    code="interaction-coverage",
                    message=(
                        "trusted input did not span the measured loading window: "
                        f"need at least {required.minimum_interaction_coverage_pct:g}% coverage"
                    ),
                )
            )
    if required.require_no_label_overflow:
        labels_overflowed = _number(payload.get("labels_overflowed"))
        if labels_overflowed is None:
            issues.append(
                PerformanceIssue(
                    kind="invalid",
                    code="attribution-retention-missing",
                    message="span-label retention provenance is missing",
                )
            )
        elif labels_overflowed != 0:
            issues.append(
                PerformanceIssue(
                    kind="invalid",
                    code="attribution-overflow",
                    message=(
                        "span-label capacity overflowed, so whole-window attribution is incomplete"
                    ),
                )
            )
    if required.require_no_resource_overflow:
        resource_overflow = _number(payload.get("resource_timing_buffer_full"))
        if resource_overflow is None:
            issues.append(
                PerformanceIssue(
                    kind="invalid",
                    code="resource-retention-missing",
                    message="Resource Timing retention provenance is missing",
                )
            )
        elif resource_overflow != 0:
            issues.append(
                PerformanceIssue(
                    kind="invalid",
                    code="resource-retention-overflow",
                    message="the Resource Timing buffer filled, so network totals are incomplete",
                )
            )
    if required.completion_field is not None and payload.get(required.completion_field) not in set(
        required.completion_values
    ):
        issues.append(
            PerformanceIssue(
                kind="invalid",
                code="measurement-incomplete",
                message=(
                    f"{required.completion_field} must be one of "
                    f"{list(required.completion_values)!r}; got "
                    f"{payload.get(required.completion_field)!r}"
                ),
            )
        )
    return issues


def budget_issues(payload: dict[str, Any], config: PerformanceConfig) -> list[PerformanceIssue]:
    """Report every absent required metric and every exceeded upper bound."""
    issues: list[PerformanceIssue] = []
    for budget in config.budgets:
        actual = _number(payload.get(budget.metric))
        if actual is None:
            if budget.required:
                issues.append(
                    PerformanceIssue(
                        kind="invalid",
                        code="metric-missing",
                        message=f"required performance metric {budget.metric!r} is missing",
                        metric=budget.metric,
                        maximum=budget.maximum,
                        policy=budget.policy,
                    )
                )
            continue
        if actual > budget.maximum:
            issues.append(
                PerformanceIssue(
                    kind="budget",
                    code="budget-exceeded",
                    message=f"{budget.metric} is {actual:g}; budget is <= {budget.maximum:g}",
                    metric=budget.metric,
                    actual=actual,
                    maximum=budget.maximum,
                    policy=budget.policy,
                )
            )
    return issues


def blocking_issues(issues: list[PerformanceIssue]) -> list[PerformanceIssue]:
    """Return invalid evidence and exceeded hard gates, not roadmap targets."""
    return [
        issue
        for issue in issues
        if issue.kind == "invalid" or (issue.kind == "budget" and issue.policy == "gate")
    ]


def format_issues(issues: list[PerformanceIssue]) -> str:
    """Render findings for a CLI error without losing their categories."""
    return "\n".join(f"- [{issue.kind}] {issue.message}" for issue in issues)
