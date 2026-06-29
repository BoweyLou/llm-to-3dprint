from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any

from llm_to_3dprint.brief import DesignBrief


@dataclass(slots=True)
class DesignValidationIssue:
    code: str
    message: str


@dataclass(slots=True)
class DesignValidationReport:
    brief_name: str
    issues: list[DesignValidationIssue] = field(default_factory=list)
    computed: dict[str, Any] = field(default_factory=dict)

    @property
    def passes(self) -> bool:
        return not self.issues


def validate_design_contract(brief: DesignBrief) -> DesignValidationReport:
    """Validate the structured design intent before CAD generation."""

    report = DesignValidationReport(
        brief_name=brief.name,
        computed={
            "outer_length": round(brief.outer_length, 2),
            "outer_width": round(brief.outer_width, 2),
            "outer_height": round(brief.outer_height, 2),
        },
    )

    intent = brief.design_intent
    if intent is None:
        _add_issue(
            report,
            "missing_design_intent",
            "Add design_intent before code generation so silhouette, smoothness, and forbidden-shape constraints are explicit.",
        )
        return report

    if not intent.silhouette:
        _add_issue(report, "missing_silhouette", "design_intent.silhouette is required.")
    if not intent.visual_style:
        _add_issue(report, "missing_visual_style", "design_intent.visual_style is required.")
    if not intent.symmetry:
        _add_issue(report, "missing_symmetry", "design_intent.symmetry is required.")
    if not intent.cross_sections:
        _add_issue(
            report,
            "missing_cross_sections",
            "design_intent.cross_sections must describe the key shape checkpoints.",
        )
    if not intent.forbidden_features:
        _add_issue(
            report,
            "missing_forbidden_features",
            "design_intent.forbidden_features must name shape drift to avoid.",
        )
    if intent.must_be_smooth and not intent.surface_continuity:
        _add_issue(
            report,
            "missing_surface_continuity",
            "design_intent.surface_continuity is required when must_be_smooth is true.",
        )
    if intent.min_wall_thickness is None:
        _add_issue(
            report,
            "missing_min_wall_thickness",
            "design_intent.min_wall_thickness is required for printable parts.",
        )
    elif brief.wall_thickness < intent.min_wall_thickness:
        _add_issue(
            report,
            "min_wall_thickness_not_met",
            (
                f"wall_thickness {brief.wall_thickness:g} {brief.units} is below "
                f"design_intent.min_wall_thickness {intent.min_wall_thickness:g} {brief.units}."
            ),
        )

    if "ramp" in brief.object_type.lower():
        _validate_ramp_slope(brief, report)
    if brief.mesh_preservation is not None or brief.drawer_stack is not None:
        _validate_mesh_preserved_drawers(brief, report)

    return report


def format_design_validation_report(report: DesignValidationReport) -> str:
    status = "PASS" if report.passes else "FAIL"
    computed_bits = [f"{key}={value}" for key, value in sorted(report.computed.items())]
    lines = [f"{status} {report.brief_name}: {', '.join(computed_bits)}"]
    for issue in report.issues:
        lines.append(f"- {issue.code}: {issue.message}")
    return "\n".join(lines)


def _validate_ramp_slope(brief: DesignBrief, report: DesignValidationReport) -> None:
    intent = brief.design_intent
    if intent is None:
        return

    rise = brief.internal_dimensions.height
    run = brief.internal_dimensions.length
    slope_degrees = round(math.degrees(math.atan(rise / run)), 2)
    report.computed["ramp_slope_degrees"] = slope_degrees

    if intent.max_slope_degrees is None:
        _add_issue(
            report,
            "missing_max_slope_degrees",
            "Ramp briefs must set design_intent.max_slope_degrees.",
        )
        return

    if slope_degrees > intent.max_slope_degrees:
        _add_issue(
            report,
            "max_slope_exceeded",
            (
                f"Computed ramp slope {slope_degrees:g} degrees exceeds "
                f"design_intent.max_slope_degrees {intent.max_slope_degrees:g}."
            ),
        )


def _validate_mesh_preserved_drawers(brief: DesignBrief, report: DesignValidationReport) -> None:
    mesh = brief.mesh_preservation
    stack = brief.drawer_stack
    if mesh is None or stack is None:
        _add_issue(
            report,
            "missing_mesh_drawer_metadata",
            "Mesh-preserved drawer briefs must provide both mesh_preservation and drawer_stack.",
        )
        return

    report.computed["drawer_count"] = stack.drawer_count
    report.computed["drawer_clearance"] = stack.clearance
    report.computed["mesh_reuse_policy"] = mesh.mesh_reuse_policy
    report.computed["skin_selection_strategy"] = stack.skin_selection_strategy
    report.computed["source_skin_shell_thickness"] = stack.source_skin_shell_thickness

    if mesh.mesh_reuse_policy != "partition_visible_mesh":
        _add_issue(
            report,
            "unsupported_mesh_reuse_policy",
            "Functional drawers require mesh_reuse_policy='partition_visible_mesh'.",
        )
    if not mesh.require_triangle_accounting:
        _add_issue(
            report,
            "triangle_accounting_not_required",
            "Mesh-preserved drawer briefs must require source triangle accounting.",
        )
    if stack.mode != "separate_removable_trays":
        _add_issue(
            report,
            "unsupported_drawer_mode",
            "Mesh-preserved drawer v1 supports only separate removable trays.",
        )
    if not (stack.min_clearance <= stack.clearance <= stack.max_clearance):
        _add_issue(
            report,
            "drawer_clearance_out_of_range",
            "Drawer clearance must stay within the declared acceptable clearance range.",
        )
    if len(stack.patch_masks) != stack.drawer_count:
        _add_issue(
            report,
            "drawer_mask_count_mismatch",
            "drawer_stack.patch_masks must define exactly one source-triangle mask per drawer.",
        )


def _add_issue(report: DesignValidationReport, code: str, message: str) -> None:
    report.issues.append(DesignValidationIssue(code=code, message=message))
