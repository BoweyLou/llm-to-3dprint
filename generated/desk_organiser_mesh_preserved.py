"""Build the mesh-preserved functional drawer conversion.

This script is intentionally mesh-first: the MakerLab surface mesh remains the
visible source of truth, while generated geometry supplies drawer function.
"""

from __future__ import annotations

from pathlib import Path

from llm_to_3dprint.brief import DesignBrief
from llm_to_3dprint.mesh_drawers import build_mesh_preserved_drawers


ROOT = Path(__file__).resolve().parents[1]
BRIEF_PATH = ROOT / "generated" / "desk_organiser_mesh_preserved_brief.json"
OUTPUT_DIR = ROOT / "generated" / "output" / "desk_organiser_mesh_preserved_drawers"


def main() -> None:
    brief = DesignBrief.load(BRIEF_PATH)
    result = build_mesh_preserved_drawers(brief, OUTPUT_DIR)
    status = "PASS" if result.passes_triangle_accounting else "FAIL"
    print(
        f"{status} {brief.name}: source_facets={result.source_facet_count}, "
        f"assigned={result.assigned_source_triangle_count}, "
        f"duplicates={result.duplicate_source_triangle_count}, "
        f"unassigned={result.unassigned_source_triangle_count}"
    )
    print(result.output_dir)


if __name__ == "__main__":
    main()
