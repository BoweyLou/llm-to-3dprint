# ADR 0001: Mesh-Preserved Drawers Use Skin And Solid Layers

- Status: Accepted
- Date: 2026-05-05

## Context

The mesh-preserved drawer workflow must retain every original source triangle exactly once across the final body and drawer-front parts. The first implementation proved that source-triangle accounting can pass while the emitted STL/3MF parts remain non-manifold and unsuitable for printing.

The source artistic mesh is valuable as exterior visual skin, but functional drawers also need clean volume geometry for backs, trays, rails, cavities, clearances, and stops.

## Decision

Treat mesh-preserved drawer output as two coordinated layers:

- an immutable source-skin layer where every original triangle is assigned exactly once
- a generated shell/functional-solid layer for closure, backing, and mechanical drawer/body geometry

Drawer-front skin selection should prefer front-visible raycasting when Open3D is installed, falling back to the dependency-free grid selector when it is not. Source-triangle accounting remains required, but manifest validation must also report slicer-closed mesh health for the mesh-preserved print output and fail non-manifold functional output.

The build writes a mesh-preserved print 3MF for the real handoff, an assembled preview 3MF for proving the original skin is present in assembled position, a source-skin-only preview 3MF for proving the original triangles are present without generated backing geometry, and a separate functional-core diagnostic 3MF for inspecting the generated drawer/body solids. The manifest records both slicer-closed health and stricter multi-shell edge topology because Bambu can accept balanced contact edges that are not a single mathematical shell.

The initial optional mesh stack is `trimesh`, `Open3D`, `manifold3d`, and sidecar review/repair tools such as Blender or PyMeshLab. Robust booleans should be used for generated solids, not for mutating preserved source triangles.

## Consequences

This makes the preservation rule more precise: source triangles are preserved as owned skin triangles, while printability comes from generated shell solids, backing, trays, and explicit closure geometry.

It also means a mesh-preserved build can now fail after triangle accounting passes. That is intentional; non-manifold geometry is a release blocker, not a slicer-cleanup detail.

The workflow has more dependencies when using the full v3 path, but the core code still works without them by falling back to the grid selector.

## Alternatives considered

- Continue tuning centroid/depth masks and projected caps. This preserves IDs but does not reliably create printable solids.
- Let Bambu Studio or another slicer repair the final mesh. This can alter geometry and is not an auditable preservation step.
- Remesh or voxelize the artistic surface. This may create printable geometry, but it violates the hard requirement to reuse original source triangles exactly once.
