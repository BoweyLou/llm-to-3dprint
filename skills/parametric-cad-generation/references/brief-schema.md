# Brief Schema

Use a JSON brief when the part is more complex than a one-off toy shape or when the user is likely to iterate.

## Core fields

- `name`: short machine-friendly part name
- `description`: human description of the part
- `object_type`: `enclosure`, `box`, `bracket`, `tray`, `fixture`, `decorative`, or similar
- `library`: usually `cadquery`; use `build123d` only when needed
- `units`: usually `mm`
- `base_shape`: use `rectangular` for box-like parts
- `internal_dimensions.length|width|height`: cavity or interior target dimensions
- `wall_thickness`: shell thickness
- `base_thickness`: floor thickness; defaults to `wall_thickness` if omitted
- `fillet_radius`: external edge softening
- `lid_style`: `open_top`, `slide_lid`, `screw_top`, or similar

## Optional feature arrays

### `cutouts`

Each cutout object may contain:

- `name`
- `face`: `front`, `back`, `left`, `right`, `top`, `bottom`
- `shape`: `rectangular` or `circular`
- `x`, `y`, `z`: center position
- `width`, `height`: for rectangular cutouts
- `diameter`: for circular cutouts
- `depth`: optional; defaults to a safe wall-penetrating depth
- `notes`

### `mounting_holes`

Each mounting hole object may contain:

- `name`
- `x`, `y`: center position on the base plane
- `diameter`
- `depth`

## Coordinate conventions

Use these defaults unless the user explicitly wants something else:

- origin is centered in X and Y
- `Z=0` is the bottom face
- `x` spans part length
- `y` spans part width
- front and back face cutouts use `x` and `z`
- left and right face cutouts use `y` and `z`
- top and bottom face cutouts use `x` and `y`

## Defaults

- enclosure walls: `2.0` to `3.0`
- default library: `cadquery`
- export targets: STL and STEP
- first-pass modeling target: simple, editable, printable geometry rather than perfect industrial design

## Current renderer scope

The bundled renderer only generates starter CadQuery code for rectangular enclosure-style parts. For other shapes:

1. still use the JSON brief
2. still run `validate` and `prompt`
3. write a custom script using the generated prompt and the user's constraints

