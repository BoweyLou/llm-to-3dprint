# Multicolor Brief Fields

Use this file when a part is multicolor, backend-specific, or expected to end as a slicer-native project.

## Minimum Intent Fields

Capture these before modeling:

- `target_backend`
  Examples: `generic`, `bambu_studio`, `prusaslicer`, `orcaslicer`
- `target_printer`
  Examples: `A1`, `P1S`, `X1C`, `MK4S`
- `multi_material_hardware`
  Examples: `none`, `ams_lite`, `ams`, `mmu`
- `filament_count`
- `final_artifact`
  Examples: `geometry_only`, `slicer_handoff`, `printer_native_project`
- `color_strategy`
  Examples: `in_place_multicolor`, `separate_inserts`, `side_by_side_parts`, `hybrid`

## Geometry-Level Fields

Use these to describe how the model should be broken up:

- `color_regions`
  A list of intended color areas or bodies
- `region_name`
- `filament`
  Integer slot or named color
- `implementation`
  Examples: `same_part_body`, `insert`, `accent_part`
- `assembled_with`
  What the region mates to, if applicable
- `flush_allowed`
  `true` only when the backend is proven
- `notes`

## Manufacturing-Level Fields

Use these when the output is more than geometry:

- `plate_strategy`
  Examples: `single_plate`, `split_plates`, `accent_side_by_side`
- `support_policy`
  Examples: `avoid_supports`, `supports_ok`, `supports_on_accents_only`
- `grouping_strategy`
  Examples: `merge_as_parts`, `separate_objects`, `hybrid`
- `filament_mapping`
  Explicit part/body to filament mapping
- `serializer`
  The final tool that writes the print project
- `seed_template`
  Optional validated project template path when the backend supports template-based output

## Validation Fields

Capture what must be proven before calling the output done:

- `require_fit_check`
- `require_non_overlap_check`
- `require_backend_export_check`
- `require_project_structure_check`
- `require_visible_multicolor_check`

## Generic Example

```json
{
  "target_backend": "generic",
  "target_printer": "unknown",
  "multi_material_hardware": "ams_like",
  "filament_count": 2,
  "final_artifact": "slicer_handoff",
  "color_strategy": "hybrid",
  "color_regions": [
    {
      "region_name": "lid_shell",
      "filament": 1,
      "implementation": "same_part_body",
      "flush_allowed": false
    },
    {
      "region_name": "lid_badge",
      "filament": 2,
      "implementation": "insert",
      "assembled_with": "lid_shell",
      "flush_allowed": false
    }
  ],
  "grouping_strategy": "hybrid",
  "plate_strategy": "accent_side_by_side",
  "serializer": "target_slicer",
  "require_fit_check": true,
  "require_non_overlap_check": true,
  "require_backend_export_check": false,
  "require_project_structure_check": false
}
```

## Bambu Mapping

If the active repo supports Bambu handoff specs, map the brief to these concepts:

- `target_backend` -> `bambu_studio`
- `multi_material_hardware` -> `ams` or `ams_lite`
- `final_artifact` -> `printer_native_project`
- `serializer` -> `Bambu Studio`
- `seed_template` -> `seed_template_3mf`
- `grouping_strategy=merge_as_parts` for in-place multicolor bodies
- `grouping_strategy=separate_objects` for standalone accents or base parts

If the repo already provides a `BambuProjectSpec`, use that instead of inventing parallel field names in code.

## Failure Rules

- If the user has not specified a target backend, do not promise a printer-native multicolor project.
- If the backend is known to be fragile, default `flush_allowed` to `false`.
- If the output depends on a template-backed slicer workflow, do not omit the template path from the brief or handoff.
