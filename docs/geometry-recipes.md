# Geometry Recipes

These recipes are repo-owned patterns for common printable shapes. They are not upstream CadQuery or build123d documentation. Use official docs for API details and this file for local modeling decisions, shape contracts, and validation expectations.

## Smooth Ramp Wedge

Use for threshold ramps, robot-vac ramps, shallow cable covers, and other contact parts that must avoid odd bumps.

Design contract:
- `silhouette`: one smooth wedge from entry lip to rear height
- `symmetry`: usually `y`
- `surface_continuity`: continuous top face with no isolated humps or abrupt local peaks
- `max_slope_degrees`: required
- `cross_sections`: centerline side profile plus left/right side profile relationship
- `forbidden_features`: isolated bumps, spikes, floating ribs, non-manifold underside pockets

Validation expectations:
- `validate-design` computes the brief-level ramp slope from height and length.
- The computed slope must not exceed `design_intent.max_slope_degrees`.
- Later CAD-level checks should verify monotonic centerline rise and edge continuity from the generated mesh or section samples.

## Rounded Enclosure Shell

Use for electronics boxes and utility housings where the internal footprint matters more than decoration.

Design contract:
- `silhouette`: simple rectangular or rounded-rect shell
- `symmetry`: `xy` when cutouts do not intentionally break it
- `surface_continuity`: flat walls with only intentional cutouts, mounting features, and fillets
- `min_wall_thickness`: required and no larger than `wall_thickness`
- `forbidden_features`: decorative ribs intruding into internal fit, random exterior bumps, unsupported wall islands

Validation expectations:
- Brief validation checks core dimensions, wall thickness, cutout bounds, and mounting-hole bounds.
- `validate-design` checks that design intent names the silhouette, symmetry, cross sections, and forbidden shape drift.
- `validate-artifacts` checks exported STL/OBJ/3MF bounds when the part is referenced by a Bambu handoff.
- CAD-level checks should still measure detailed wall assumptions inside the CAD kernel when precise enclosure wall proof is required.

## Friction Or Snap Lid

Use for two-part enclosures with seated lids, lips, tabs, or snap/friction fit.

Design contract:
- `closure`: required for non-open-top lids
- `surface_continuity`: mating lip and exterior styling must stay on their intended sides
- `cross_sections`: at least one lid section and one base-seat section
- `forbidden_features`: mating features on decorative face, styling that changes fit clearance

Validation expectations:
- Brief validation derives or checks `resolved_lid_seat_z`.
- Existing `check-fit` verifies the generated base/lid script when it exposes the expected fit-check functions or constants.
- Later recipe work should add snap tab spacing and clearance-specific checks.

## Keyed Seam

Use for multi-segment prints that need alignment without obvious top-surface artifacts.

Design contract:
- `silhouette`: continuous outer profile across segment boundaries
- `symmetry`: match the parent part unless the seam is intentionally asymmetric
- `cross_sections`: seam section plus top-surface section through the connector
- `forbidden_features`: visible top-surface bulges, over-deep pockets, thin unsupported connector walls

Validation expectations:
- Brief-level validation should require seam cross-section descriptions.
- CAD-level checks should later compare adjacent segment bounds and connector clearances.

## Jigsaw Seam

Use when printed segments need larger mechanical registration than a small key can provide.

Design contract:
- `silhouette`: continuous outer footprint with deliberate interlocking seam geometry
- `surface_continuity`: top contact surface should remain smooth across the join
- `forbidden_features`: sharp stress risers, tiny fragile teeth, asymmetric accidental tooth spacing

Validation expectations:
- Brief-level validation should require seam and side-profile cross sections.
- CAD-level checks should later measure tooth depth, neck width, and print-clearance assumptions.

## Multi-Part Plate Split

Use when a part is too large for the target bed or needs separate color/material groups.

Design contract:
- `silhouette`: full assembly silhouette plus each plate segment silhouette
- `cross_sections`: at least one section through each split interface
- `forbidden_features`: stale STL intermediates, unaligned segment origins, plate parts exceeding target bed

Validation expectations:
- Bambu handoff validation owns printer/project fields.
- Brief-level validation owns design intent and shape-contract completeness.
- `validate-artifacts` compares generated artifact bounds against known target bed constraints before Bambu export.

## Mesh-Preserved Functional Drawers

Use when a one-piece artistic mesh must remain the visible source of truth but needs functional drawers or inserts.

Design contract:
- `mesh_preservation`: required, with `mesh_reuse_policy` set to `partition_visible_mesh`
- `drawer_stack`: required, with `mode` set to `separate_removable_trays`
- `source 3MF`: preserved source mesh, not merely a visual reference
- `clearance`: usually 0.4-0.6 mm for FDM sliding drawers
- `forbidden_features`: dropped source triangles, duplicated source triangles, remeshed drawer fronts, decimated surface detail
- `cross_sections`: front drawer stack, drawer tray section, and fixed-body cavity section

Validation expectations:
- `validate-design` checks that drawer metadata and triangle accounting are explicit.
- `build-mesh-drawers` treats drawer masks as coarse regions, then selects only the front-visible connected skin for each drawer before adding generated shell, backing, and tray geometry behind it. Prefer `front_visible_raycast` when Open3D is installed; the grid selector is a dependency-free fallback.
- For sculpted drawer fronts, keep `front_normal_min_y` high enough to select the visible face and handle surfaces without pulling recessed side facets into the removable drawer skin. This avoids shell-closure fins while preserving every source triangle exactly once across the output parts.
- Drawer-front source skins should be closed against flat backing caps, not by duplicating the full sculpted source patch behind itself. The body can keep a conformal shell, but drawer fronts need the cleaner backing method so line relief and cross-hatch boundaries do not become visible physical fins.
- `build-mesh-drawers` emits a mesh-preserved print 3MF with source skins plus generated shell/backing geometry, an assembled preview 3MF for visual confirmation of the full preserved-skin parts, a front-review 3MF for drawer-side Bambu previews, a source-skin preview 3MF containing only the original source triangles, and a functional-core diagnostic 3MF with only clean generated solids.
- `validate-mesh-manifest` must report zero unassigned and zero duplicated source triangles, functional drawer clearances within the configured range, zero open/oriented boundary errors on the mesh-preserved print output, and must fail non-manifold functional-core parts.
- STL/3MF are the authoritative deliverables because STEP does not faithfully carry the preserved triangle skin.
- Source-triangle accounting is necessary but not sufficient. A passing manifest must also report slicer-closed geometry health for the mesh-preserved print output; Bambu non-manifold/open-edge reports are release blockers, not harmless slicer-review noise.
