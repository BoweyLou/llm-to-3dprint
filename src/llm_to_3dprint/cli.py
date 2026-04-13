from __future__ import annotations

import argparse
from pathlib import Path

from llm_to_3dprint.bambu import (
    DEFAULT_BAMBU_GUI_APP_PATH,
    DEFAULT_BAMBU_GUI_CLICK_BACKEND,
    DEFAULT_BAMBU_GUI_MERGE_CLICK,
    BambuProjectSpec,
    apply_seed_template_3mf,
    build_bambu_handoff,
    capture_seed_template_3mf,
    check_seed_template_3mf,
    export_3mf_with_bambu_cli,
    export_3mf_with_bambu_gui,
    format_bambu_cli_export_result,
    format_bambu_gui_export_result,
    format_bambu_hammerspoon_setup_result,
    format_bambu_patch_result,
    format_bambu_probe,
    format_bambu_template_capture_result,
    format_bambu_template_check_result,
    probe_bambu_studio,
    preset_a1_hybrid_two_color,
    patch_studio_3mf_multicolor,
    setup_hammerspoon_for_bambu,
    SUPPORTED_GUI_CLICK_BACKENDS,
    write_cli_assemble_list,
)
from llm_to_3dprint.bambu_mcp import main as bambu_mcp_main
from llm_to_3dprint.brief import DesignBrief, preset_rectangular_enclosure
from llm_to_3dprint.fitcheck import FitCheckError, check_script_fit
from llm_to_3dprint.prompting import build_generation_prompt
from llm_to_3dprint.renderers import render_script


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llm-to-3dprint",
        description="Structured briefs, prompts, and starter scripts for LLM-guided CAD generation.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-brief", help="Write a starter design brief JSON file.")
    init_parser.add_argument("--output", "-o", required=True, help="Path to the JSON file to create.")
    init_parser.add_argument(
        "--preset",
        default="rectangular-enclosure",
        choices=["rectangular-enclosure"],
        help="Starter preset to write.",
    )

    validate_parser = subparsers.add_parser("validate", help="Validate a design brief JSON file.")
    validate_parser.add_argument("brief", help="Path to the JSON brief.")

    prompt_parser = subparsers.add_parser("prompt", help="Generate an LLM prompt from a brief.")
    prompt_parser.add_argument("brief", help="Path to the JSON brief.")
    prompt_parser.add_argument("--output", "-o", help="Optional file to write instead of stdout.")

    render_parser = subparsers.add_parser("render", help="Render a starter Python CAD script.")
    render_parser.add_argument("brief", help="Path to the JSON brief.")
    render_parser.add_argument("--output", "-o", required=True, help="Path to the Python file to write.")

    fit_parser = subparsers.add_parser(
        "check-fit",
        help="Check whether an enclosure base/lid script seats without interference.",
    )
    fit_parser.add_argument("script", help="Path to the generated Python CAD script.")

    init_bambu_parser = subparsers.add_parser(
        "init-bambu-project",
        help="Write a starter Bambu Studio handoff JSON file.",
    )
    init_bambu_parser.add_argument("--output", "-o", required=True, help="Path to the JSON file to create.")
    init_bambu_parser.add_argument(
        "--preset",
        default="a1-hybrid-two-color",
        choices=["a1-hybrid-two-color"],
        help="Starter Bambu handoff preset to write.",
    )

    validate_bambu_parser = subparsers.add_parser(
        "validate-bambu-project",
        help="Validate a Bambu Studio handoff JSON file.",
    )
    validate_bambu_parser.add_argument("project", help="Path to the Bambu handoff JSON file.")

    handoff_parser = subparsers.add_parser(
        "bambu-handoff",
        help="Render a Bambu Studio import/save plan from a handoff JSON file.",
    )
    handoff_parser.add_argument("project", help="Path to the Bambu handoff JSON file.")
    handoff_parser.add_argument("--output", "-o", help="Optional file to write instead of stdout.")

    probe_parser = subparsers.add_parser(
        "bambu-probe",
        help="Inspect the local Bambu Studio installation and automation prerequisites.",
    )
    probe_parser.add_argument(
        "--app-path",
        default="/Applications/BambuStudio.app",
        help="Override the Bambu Studio app bundle path.",
    )

    setup_hammerspoon_parser = subparsers.add_parser(
        "bambu-setup-hammerspoon",
        help="Install the minimal hs.ipc bootstrap block for Hammerspoon and verify the repo-managed Bambu actions can be used.",
    )
    setup_hammerspoon_parser.add_argument(
        "--app-path",
        default=DEFAULT_BAMBU_GUI_APP_PATH,
        help="Override the Bambu Studio app bundle path used during verification.",
    )
    setup_hammerspoon_parser.add_argument(
        "--no-restart",
        action="store_true",
        help="Write the init block without restarting Hammerspoon.",
    )

    build_cli_parser = subparsers.add_parser(
        "bambu-build-cli",
        help="Write a Bambu Studio CLI assemble-list JSON from a Bambu handoff spec.",
    )
    build_cli_parser.add_argument("project", help="Path to the Bambu handoff JSON file.")
    build_cli_parser.add_argument("--output", "-o", required=True, help="Path to the assemble-list JSON file.")

    export_cli_parser = subparsers.add_parser(
        "bambu-export-cli",
        help="Attempt a Bambu Studio CLI export to a printer-facing .3mf from a Bambu handoff spec.",
    )
    export_cli_parser.add_argument("project", help="Path to the Bambu handoff JSON file.")
    export_cli_parser.add_argument("--output", "-o", help="Optional override path for the output .3mf.")
    export_cli_parser.add_argument(
        "--assemble-output",
        help="Optional path to also write the intermediate assemble-list JSON.",
    )

    export_gui_parser = subparsers.add_parser(
        "bambu-export-gui",
        help="Export a printer-facing .3mf by driving Bambu Studio's GUI and saving the project.",
    )
    export_gui_parser.add_argument("project", help="Path to the Bambu handoff JSON file.")
    export_gui_parser.add_argument("--output", "-o", help="Optional override path for the output .3mf.")
    export_gui_parser.add_argument(
        "--app-path",
        default=DEFAULT_BAMBU_GUI_APP_PATH,
        help="Override the Bambu Studio app bundle path.",
    )
    export_gui_parser.add_argument(
        "--merge-click-x",
        type=int,
        default=DEFAULT_BAMBU_GUI_MERGE_CLICK[0],
        help="Screen X coordinate used to confirm the multipart merge dialog.",
    )
    export_gui_parser.add_argument(
        "--merge-click-y",
        type=int,
        default=DEFAULT_BAMBU_GUI_MERGE_CLICK[1],
        help="Screen Y coordinate used to confirm the multipart merge dialog.",
    )
    export_gui_parser.add_argument(
        "--import-timeout",
        type=float,
        default=30.0,
        help="Seconds to wait for the import flow to settle.",
    )
    export_gui_parser.add_argument(
        "--save-timeout",
        type=float,
        default=30.0,
        help="Seconds to wait for the save flow and output file to appear.",
    )
    export_gui_parser.add_argument(
        "--click-backend",
        default=DEFAULT_BAMBU_GUI_CLICK_BACKEND,
        choices=sorted(SUPPORTED_GUI_CLICK_BACKENDS),
        help="Backend used for the merge-confirmation click. 'auto' prefers Hammerspoon when ready.",
    )

    patch_parser = subparsers.add_parser(
        "bambu-patch-3mf",
        help="Patch a Studio-authored .3mf with multicolor filament/object metadata using a Bambu handoff spec.",
    )
    patch_parser.add_argument("project", help="Path to the Bambu handoff JSON file.")
    patch_parser.add_argument("input_3mf", help="Path to the Studio-authored .3mf to patch.")
    patch_parser.add_argument("--output", "-o", required=True, help="Path to the patched .3mf file.")

    template_parser = subparsers.add_parser(
        "bambu-apply-template",
        help="Patch a seed Bambu Studio .3mf template into a fresh output using a Bambu handoff spec.",
    )
    template_parser.add_argument("project", help="Path to the Bambu handoff JSON file.")
    template_parser.add_argument(
        "--template",
        help="Optional override path for the seed Bambu Studio .3mf template.",
    )
    template_parser.add_argument(
        "--output",
        "-o",
        help="Optional override path for the final patched .3mf. Defaults to output_3mf from the spec.",
    )

    check_template_parser = subparsers.add_parser(
        "bambu-check-template",
        help="Validate that a Studio-authored seed .3mf template matches the in-place multicolor parts in a Bambu handoff spec.",
    )
    check_template_parser.add_argument("project", help="Path to the Bambu handoff JSON file.")
    check_template_parser.add_argument(
        "--template",
        help="Optional override path for the seed Bambu Studio .3mf template.",
    )

    capture_template_parser = subparsers.add_parser(
        "bambu-capture-template",
        help="Validate and copy a Studio-authored .3mf into the seed-template path for a Bambu handoff spec.",
    )
    capture_template_parser.add_argument("project", help="Path to the Bambu handoff JSON file.")
    capture_template_parser.add_argument("input_3mf", help="Path to the Studio-authored .3mf to capture.")
    capture_template_parser.add_argument(
        "--output",
        "-o",
        help="Optional override path for the captured seed template. Defaults to seed_template_3mf from the spec.",
    )
    capture_template_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting an existing captured seed template.",
    )

    subparsers.add_parser(
        "bambu-mcp-server",
        help="Run the Bambu stdio MCP server for end-to-end automation.",
    )

    return parser


def write_text(path: str | Path, content: str) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init-brief":
        if args.preset != "rectangular-enclosure":
            raise SystemExit(f"Unsupported preset: {args.preset}")
        preset_rectangular_enclosure().dump(args.output)
        print(f"Wrote starter brief to {args.output}")
        return

    if args.command == "validate":
        brief = DesignBrief.load(args.brief)
        print(
            "Validated "
            f"{brief.name}: outer {brief.outer_length:.1f} x {brief.outer_width:.1f} x {brief.outer_height:.1f} {brief.units}"
        )
        return

    if args.command == "prompt":
        brief = DesignBrief.load(args.brief)
        prompt = build_generation_prompt(brief)
        if args.output:
            write_text(args.output, prompt)
            print(f"Wrote prompt to {args.output}")
        else:
            print(prompt)
        return

    if args.command == "render":
        brief = DesignBrief.load(args.brief)
        script = render_script(brief)
        write_text(args.output, script)
        print(f"Wrote script to {args.output}")
        return

    if args.command == "check-fit":
        try:
            result = check_script_fit(args.script)
        except FitCheckError as exc:
            raise SystemExit(str(exc)) from exc

        status = "PASS" if result.passes else "FAIL"
        print(
            f"{status} {args.script}: seat_z={result.seat_z:.3f}, "
            f"overlap_solids={result.overlap_solids}, "
            f"overlap_volume={result.overlap_volume:.6f}"
        )
        return

    if args.command == "init-bambu-project":
        if args.preset != "a1-hybrid-two-color":
            raise SystemExit(f"Unsupported preset: {args.preset}")
        preset_a1_hybrid_two_color().dump(args.output)
        print(f"Wrote starter Bambu handoff to {args.output}")
        return

    if args.command == "validate-bambu-project":
        spec = BambuProjectSpec.load(args.project)
        print(
            "Validated "
            f"{spec.name}: printer={spec.target_printer}, "
            f"filaments={spec.filament_count}, parts={len(spec.parts)}, "
            f"backend={spec.export_backend}"
        )
        return

    if args.command == "bambu-handoff":
        spec = BambuProjectSpec.load(args.project)
        handoff = build_bambu_handoff(spec)
        if args.output:
            write_text(args.output, handoff)
            print(f"Wrote Bambu handoff plan to {args.output}")
        else:
            print(handoff)
        return

    if args.command == "bambu-probe":
        print(format_bambu_probe(probe_bambu_studio(args.app_path)))
        return

    if args.command == "bambu-setup-hammerspoon":
        result = setup_hammerspoon_for_bambu(
            app_path=args.app_path,
            restart=not args.no_restart,
        )
        print(format_bambu_hammerspoon_setup_result(result))
        if not result.success:
            raise SystemExit(1)
        return

    if args.command == "bambu-build-cli":
        spec = BambuProjectSpec.load(args.project)
        destination = write_cli_assemble_list(spec, args.output)
        print(f"Wrote Bambu CLI assemble list to {destination}")
        return

    if args.command == "bambu-export-cli":
        spec = BambuProjectSpec.load(args.project)
        result = export_3mf_with_bambu_cli(
            spec,
            output_3mf=args.output,
            assemble_list_path=args.assemble_output,
        )
        print(format_bambu_cli_export_result(result))
        if not result.success:
            raise SystemExit(1)
        return

    if args.command == "bambu-export-gui":
        spec = BambuProjectSpec.load(args.project)
        result = export_3mf_with_bambu_gui(
            spec,
            output_3mf=args.output,
            app_path=args.app_path,
            merge_click=(args.merge_click_x, args.merge_click_y),
            click_backend=args.click_backend,
            import_timeout=args.import_timeout,
            save_timeout=args.save_timeout,
        )
        print(format_bambu_gui_export_result(result))
        if not result.success:
            raise SystemExit(1)
        return

    if args.command == "bambu-patch-3mf":
        spec = BambuProjectSpec.load(args.project)
        result = patch_studio_3mf_multicolor(spec, args.input_3mf, output_3mf=args.output)
        print(format_bambu_patch_result(result))
        if not result.success:
            raise SystemExit(1)
        return

    if args.command == "bambu-apply-template":
        spec = BambuProjectSpec.load(args.project)
        result = apply_seed_template_3mf(
            spec,
            output_3mf=args.output,
            seed_template_3mf=args.template,
        )
        print(format_bambu_patch_result(result))
        if not result.success:
            raise SystemExit(1)
        return

    if args.command == "bambu-check-template":
        spec = BambuProjectSpec.load(args.project)
        result = check_seed_template_3mf(spec, seed_template_3mf=args.template)
        print(format_bambu_template_check_result(result))
        if not result.success:
            raise SystemExit(1)
        return

    if args.command == "bambu-capture-template":
        spec = BambuProjectSpec.load(args.project)
        result = capture_seed_template_3mf(
            spec,
            args.input_3mf,
            output_3mf=args.output,
            overwrite=args.overwrite,
        )
        print(format_bambu_template_capture_result(result))
        if not result.success:
            raise SystemExit(1)
        return

    if args.command == "bambu-mcp-server":
        bambu_mcp_main()
        return

    raise SystemExit(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    main()
