You are generating a Python CAD script.

Target library: cadquery
Object name: rectangular_enclosure_demo
Object type: enclosure
Units: mm
Base shape: rectangular

Description:
Open-top electronics enclosure with a front display cutout and four base mounting holes.

Core dimensions:
- internal length: 80.0
- internal width: 50.0
- internal height: 25.0
- wall thickness: 2.0
- base thickness: 2.5
- fillet radius: 2.0
- lid style: open_top

Cutouts:
- front_display: face=front, shape=rectangular, x=0.0, y=0.0, z=14.0, width=40.0, height=20.0, depth=4.0
- side_cable: face=right, shape=circular, x=0.0, y=0.0, z=9.0, diameter=8.0, depth=4.0

Mounting holes:
- front_left: x=-28.0, y=16.0, diameter=3.2, depth=3.0
- front_right: x=28.0, y=16.0, diameter=3.2, depth=3.0
- rear_left: x=-28.0, y=-16.0, diameter=3.2, depth=3.0
- rear_right: x=28.0, y=-16.0, diameter=3.2, depth=3.0

Requirements:
- Keep the interior footprint clear for a PCB and wiring.
- Avoid overhangs that require support in a standard FDM print orientation.
- Use relative references wherever possible.

Notes:
- Origin is centered in X and Y, with Z measured from the base upward.
- This preset is deliberately simple and meant as a starting point.

Coordinate conventions:
- origin is centered in X and Y
- Z=0 is the bottom face
- X spans the enclosure length
- Y spans the enclosure width
- cutout coordinates describe the center of the feature

Generate a complete Python script that:
1. Defines every critical dimension as a named parameter near the top of the file.
2. Uses relative references and reusable helper functions where practical.
3. Builds the final solid in cadquery.
4. Exports both STL and STEP files.
5. Includes brief comments explaining parameter groups and coordinate assumptions.
6. Avoids brittle absolute magic numbers.

If geometry is ambiguous, choose conservative printable defaults and state them in code comments.
