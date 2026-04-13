You are generating a Python CAD script.

Target library: cadquery
Object name: esp32_dev_board_enclosure
Object type: enclosure
Units: mm
Base shape: rectangular

Description:
Two-part enclosure for a generic ESP32 development board with a USB-side cable opening and friction-fit lid.

Core dimensions:
- internal length: 66.0
- internal width: 39.0
- internal height: 19.0
- wall thickness: 2.4
- base thickness: 2.8
- fillet radius: 2.0
- lid style: friction_lid

Cutouts:
- usb_opening: face=left, shape=rectangular, x=0.0, y=0.0, z=10.8, width=12.0, height=8.0, depth=4.0

Mounting holes:
- No mounting holes requested.

Requirements:
- Assume a generic ESP32 dev board envelope of roughly 52 x 29 x 14 mm.
- Keep the enclosure printable without supports with the base and lid printed separately.
- Provide a USB cable cutout on one short wall.
- Use parameterized dimensions so board fit can be adjusted quickly.

Notes:
- Default dimensions are intended for a common ESP32 dev board and should be adjusted for the exact PCB.
- The custom generated script adds board support pads, corner locators, and a friction-fit lid.

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
