from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
import json
import plistlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
import zipfile
from typing import Any, Sequence

SUPPORTED_AMS_TYPES = {"none", "ams_lite", "ams"}
SUPPORTED_EXPORT_BACKENDS = {
    "bambu_studio_gui",
    "bambu_studio_cli",
    "bambu_studio_mcp",
    "clean_room_3mf",
}
DEFAULT_BAMBU_GUI_APP_PATH = "/Applications/BambuStudio.app"
DEFAULT_BAMBU_GUI_MERGE_CLICK = (1170, 643)
DEFAULT_BAMBU_GUI_CLICK_BACKEND = "auto"
DEFAULT_BAMBU_FILAMENT_COLORS = [
    "#FFFF00",
    "#FF6A00",
    "#00A2FF",
    "#7E57C2",
    "#00C853",
    "#FF4D6D",
]
SUPPORTED_LOAD_STRATEGIES = {"merge_as_parts", "separate_object"}
SUPPORTED_PRINT_MODES = {"standalone", "in_place_multicolor", "side_by_side_accent"}
SUPPORTED_MODEL_SUFFIXES = {".stl", ".step", ".3mf", ".obj"}
SUPPORTED_CLI_MESH_SUFFIXES = {".stl", ".obj"}
SUPPORTED_GUI_CLICK_BACKENDS = {"auto", "swift", "hammerspoon"}
HAMMERSPOON_INIT_MARKER_START = "-- BEGIN llm_to_3dprint managed hs.ipc block"
HAMMERSPOON_INIT_MARKER_END = "-- END llm_to_3dprint managed hs.ipc block"


@dataclass(slots=True)
class BambuPartSpec:
    name: str
    path: str
    object_name: str | None = None
    part_name: str | None = None
    load_strategy: str = "separate_object"
    print_mode: str = "standalone"
    plate: int = 1
    filament: int = 1
    notes: str = ""

    def validate(self) -> None:
        if not self.name:
            raise ValueError("part.name must not be empty")
        if not self.path:
            raise ValueError("part.path must not be empty")
        suffix = Path(self.path).suffix.lower()
        if suffix not in SUPPORTED_MODEL_SUFFIXES:
            raise ValueError(
                f"part.path must end with one of {sorted(SUPPORTED_MODEL_SUFFIXES)}, got {self.path!r}"
            )
        if self.load_strategy not in SUPPORTED_LOAD_STRATEGIES:
            raise ValueError(
                "part.load_strategy must be one of "
                f"{sorted(SUPPORTED_LOAD_STRATEGIES)}, got {self.load_strategy!r}"
            )
        if self.print_mode not in SUPPORTED_PRINT_MODES:
            raise ValueError(
                f"part.print_mode must be one of {sorted(SUPPORTED_PRINT_MODES)}, got {self.print_mode!r}"
            )
        if self.plate < 1:
            raise ValueError(f"part.plate must be >= 1, got {self.plate!r}")
        if self.filament < 1:
            raise ValueError(f"part.filament must be >= 1, got {self.filament!r}")
        if self.load_strategy == "merge_as_parts" and not self.object_name:
            raise ValueError("part.object_name is required when load_strategy='merge_as_parts'")
        if self.print_mode == "in_place_multicolor" and self.load_strategy != "merge_as_parts":
            raise ValueError("in_place_multicolor parts must use load_strategy='merge_as_parts'")
        if self.print_mode == "side_by_side_accent" and self.load_strategy != "separate_object":
            raise ValueError("side_by_side_accent parts must use load_strategy='separate_object'")


@dataclass(slots=True)
class BambuProjectSpec:
    name: str
    description: str
    target_printer: str
    nozzle_diameter: float
    ams: str
    filament_count: int
    export_backend: str
    output_3mf: str
    seed_template_3mf: str | None = None
    source_brief: str | None = None
    parts: list[BambuPartSpec] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.name:
            raise ValueError("name must not be empty")
        if not self.description:
            raise ValueError("description must not be empty")
        if not self.target_printer:
            raise ValueError("target_printer must not be empty")
        if self.nozzle_diameter <= 0:
            raise ValueError(f"nozzle_diameter must be > 0, got {self.nozzle_diameter!r}")
        if self.ams not in SUPPORTED_AMS_TYPES:
            raise ValueError(f"ams must be one of {sorted(SUPPORTED_AMS_TYPES)}, got {self.ams!r}")
        if self.filament_count < 1:
            raise ValueError(f"filament_count must be >= 1, got {self.filament_count!r}")
        if self.ams == "none" and self.filament_count != 1:
            raise ValueError("filament_count must be 1 when ams='none'")
        if self.ams == "ams_lite" and self.filament_count > 4:
            raise ValueError("AMS lite supports at most 4 filaments")
        if self.export_backend not in SUPPORTED_EXPORT_BACKENDS:
            raise ValueError(
                "export_backend must be one of "
                f"{sorted(SUPPORTED_EXPORT_BACKENDS)}, got {self.export_backend!r}"
            )
        if not self.output_3mf or Path(self.output_3mf).suffix.lower() != ".3mf":
            raise ValueError("output_3mf must end with '.3mf'")
        if self.seed_template_3mf is not None and Path(self.seed_template_3mf).suffix.lower() != ".3mf":
            raise ValueError("seed_template_3mf must end with '.3mf' when provided")
        if not self.parts:
            raise ValueError("parts must not be empty")

        grouped: dict[str, list[BambuPartSpec]] = defaultdict(list)
        for part in self.parts:
            part.validate()
            if part.filament > self.filament_count:
                raise ValueError(
                    f"part {part.name!r} references filament {part.filament}, "
                    f"but filament_count={self.filament_count}"
                )
            if part.object_name:
                grouped[part.object_name].append(part)

        for object_name, parts in grouped.items():
            merged_parts = [part for part in parts if part.load_strategy == "merge_as_parts"]
            if merged_parts and len(merged_parts) < 2:
                raise ValueError(
                    f"object {object_name!r} uses merge_as_parts but only defines one part"
                )
            if merged_parts:
                plates = {part.plate for part in merged_parts}
                if len(plates) != 1:
                    raise ValueError(
                        f"object {object_name!r} merge_as_parts entries must share one plate"
                    )
            if any(part.print_mode == "in_place_multicolor" for part in parts):
                in_place_parts = [part for part in parts if part.print_mode == "in_place_multicolor"]
                if len(in_place_parts) < 2:
                    raise ValueError(
                        f"object {object_name!r} needs at least two in_place_multicolor parts"
                    )
                filaments = {part.filament for part in in_place_parts}
                if len(filaments) < 2:
                    raise ValueError(
                        f"object {object_name!r} in_place_multicolor parts must use multiple filaments"
                    )
                if any(part.load_strategy != "merge_as_parts" for part in in_place_parts):
                    raise ValueError(
                        f"object {object_name!r} in_place_multicolor parts must merge as parts"
                    )

    def grouped_objects(self) -> dict[str, list[BambuPartSpec]]:
        grouped: dict[str, list[BambuPartSpec]] = defaultdict(list)
        for part in self.parts:
            if part.object_name:
                grouped[part.object_name].append(part)
        return dict(grouped)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BambuProjectSpec":
        spec = cls(
            name=payload["name"],
            description=payload["description"],
            target_printer=payload["target_printer"],
            nozzle_diameter=payload.get("nozzle_diameter", 0.4),
            ams=payload.get("ams", "none"),
            filament_count=payload.get("filament_count", 1),
            export_backend=payload.get("export_backend", "bambu_studio_gui"),
            output_3mf=payload["output_3mf"],
            seed_template_3mf=payload.get("seed_template_3mf"),
            source_brief=payload.get("source_brief"),
            parts=[BambuPartSpec(**item) for item in payload.get("parts", [])],
            notes=payload.get("notes", []),
        )
        spec.validate()
        return spec

    @classmethod
    def load(cls, path: str | Path) -> "BambuProjectSpec":
        payload = json.loads(Path(path).read_text())
        return cls.from_dict(payload)

    def dump(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2) + "\n")


@dataclass(slots=True)
class BambuStudioProbe:
    installed: bool
    app_path: str
    executable_path: str
    support_dir: str
    version: str | None
    cli_available: bool
    assistive_access: bool | None
    assistive_access_error: str | None = None
    hammerspoon_cli_path: str | None = None
    hammerspoon_cli_available: bool = False
    hammerspoon_ipc_ready: bool | None = None
    hammerspoon_error: str | None = None
    hammerspoon_accessibility_granted: bool | None = None
    hammerspoon_accessibility_error: str | None = None


@dataclass(slots=True)
class BambuPresetBundle:
    machine_path: str
    process_path: str
    filament_paths: list[str]


@dataclass(slots=True)
class BambuCliExportResult:
    command: list[str]
    output_3mf: str
    assemble_list_path: str
    presets: BambuPresetBundle
    returncode: int | None
    stdout: str
    stderr: str
    output_exists: bool
    crash_report: str | None = None

    @property
    def success(self) -> bool:
        return self.returncode == 0 and self.output_exists


@dataclass(slots=True)
class BambuGuiExportResult:
    command: list[str]
    output_3mf: str
    import_paths: list[str]
    launch_returncode: int | None
    stdout: str
    stderr: str
    output_exists: bool
    merge_dialog_clicked: bool
    save_panel_handled: bool
    click_backend_used: str | None = None
    error_text: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.launch_returncode == 0 and self.output_exists and self.error_text is None


@dataclass(slots=True)
class BambuStudio3mfPatchResult:
    input_3mf: str
    output_3mf: str
    filament_count: int
    nozzle_count: int
    patched_objects: list[str]
    output_exists: bool
    patched: bool
    error_text: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.error_text is None and self.output_exists


@dataclass(slots=True)
class BambuStudioTemplateCheckResult:
    template_3mf: str
    expected_patchable_objects: list[str]
    matched_patchable_objects: list[str]
    missing_patchable_objects: list[str]
    nozzle_count: int
    template_exists: bool
    error_text: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return (
            self.error_text is None
            and self.template_exists
            and self.nozzle_count == 1
            and not self.missing_patchable_objects
        )


@dataclass(slots=True)
class BambuStudioTemplateCaptureResult:
    input_3mf: str
    output_3mf: str
    copied: bool
    overwrite: bool
    output_exists: bool
    template_check: BambuStudioTemplateCheckResult
    error_text: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return (
            self.error_text is None
            and self.copied
            and self.output_exists
            and self.template_check.success
        )


@dataclass(slots=True)
class BambuHammerspoonSetupResult:
    init_path: str
    actions_path: str
    init_existed: bool
    init_written: bool
    restart_requested: bool
    restart_succeeded: bool
    probe: BambuStudioProbe
    error_text: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return (
            self.error_text is None
            and self.restart_succeeded
            and self.probe.hammerspoon_cli_available
            and self.probe.hammerspoon_ipc_ready is True
        )


def preset_a1_hybrid_two_color() -> BambuProjectSpec:
    return BambuProjectSpec.from_dict(
        {
            "name": "esp32_retro_futurist_a1_handoff",
            "description": (
                "Bambu Studio handoff for the retro-futurist ESP32 enclosure using a hybrid "
                "two-color workflow on an A1 with AMS lite."
            ),
            "target_printer": "A1",
            "nozzle_diameter": 0.4,
            "ams": "ams_lite",
            "filament_count": 2,
            "export_backend": "bambu_studio_cli",
            "output_3mf": "generated/output/esp32_dev_board_enclosure_retro_futurist_a1_profile.3mf",
            "seed_template_3mf": "generated/output/esp32_dev_board_enclosure_retro_futurist_a1_seed_template.3mf",
            "source_brief": "generated/esp32_dev_board_enclosure_retro_futurist_brief.json",
            "parts": [
                {
                    "name": "retro_lid_shell",
                    "path": "generated/output/esp32_dev_board_enclosure_retro_futurist_lid_shell.step",
                    "object_name": "retro_lid",
                    "part_name": "lid_shell",
                    "load_strategy": "merge_as_parts",
                    "print_mode": "in_place_multicolor",
                    "plate": 1,
                    "filament": 1,
                    "notes": "Main lid body for filament 1.",
                },
                {
                    "name": "retro_lid_inserts",
                    "path": "generated/output/esp32_dev_board_enclosure_retro_futurist_lid_inserts.step",
                    "object_name": "retro_lid",
                    "part_name": "lid_inserts",
                    "load_strategy": "merge_as_parts",
                    "print_mode": "in_place_multicolor",
                    "plate": 1,
                    "filament": 2,
                    "notes": "In-place color accents for filament 2.",
                },
                {
                    "name": "retro_lid_accent",
                    "path": "generated/output/esp32_dev_board_enclosure_retro_futurist_lid_accent.stl",
                    "part_name": "lid_accent",
                    "load_strategy": "separate_object",
                    "print_mode": "side_by_side_accent",
                    "plate": 1,
                    "filament": 2,
                    "notes": "Separate printed accent that stays side-by-side on the plate.",
                },
                {
                    "name": "retro_base",
                    "path": "generated/output/esp32_dev_board_enclosure_retro_futurist_base.stl",
                    "part_name": "base",
                    "load_strategy": "separate_object",
                    "print_mode": "standalone",
                    "plate": 2,
                    "filament": 1,
                    "notes": "Base printed on its own plate to keep the lid workflow clean.",
                },
            ],
            "notes": [
                "Use Bambu Studio as the final 3MF serializer. Raw STEP/STL imports are only geometry handoff.",
                "The preferred automation path is Studio GUI or an MCP wrapper that drives Studio end-to-end.",
                "Use Studio CLI only on hosts where --export-3mf has been verified to work without crashing.",
            ],
        }
    )


def build_bambu_handoff(spec: BambuProjectSpec) -> str:
    grouped = spec.grouped_objects()
    lines = [
        f"# Bambu Handoff: {spec.name}",
        "",
        f"- Target printer: {spec.target_printer}",
        f"- Nozzle: {spec.nozzle_diameter:.1f} mm",
        f"- AMS: {spec.ams}",
        f"- Filaments: {spec.filament_count}",
        f"- Export backend: {spec.export_backend}",
        f"- Final project: {spec.output_3mf}",
        *( [f"- Seed template: {spec.seed_template_3mf}"] if spec.seed_template_3mf else [] ),
        "",
        "## Why This Exists",
        "",
        "This spec assumes Bambu Studio is the authoritative serializer for the final .3mf print profile.",
        "Raw STEP/STL files carry geometry, but the printer-facing project also needs part grouping, filament",
        "assignment, plate placement, and printer-specific settings.",
        "",
        "## Import Plan",
        "",
    ]

    for object_name, parts in sorted(grouped.items()):
        ordered_parts = sorted(parts, key=lambda part: (part.plate, part.filament, part.name))
        lines.append(
            f"1. Import these files together as one object with multiple parts for `{object_name}` on plate {ordered_parts[0].plate}:"
        )
        for part in ordered_parts:
            part_label = part.part_name or part.name
            lines.append(
                f"   - `{part.path}` as `{part_label}` using filament {part.filament}"
            )

    separate_parts = sorted(
        [part for part in spec.parts if part.load_strategy == "separate_object"],
        key=lambda part: (part.plate, part.filament, part.name),
    )
    if separate_parts:
        lines.extend(
            [
                "",
                "## Separate Objects",
                "",
            ]
        )
        for index, part in enumerate(separate_parts, start=1):
            part_label = part.part_name or part.name
            lines.append(
                f"{index}. Import `{part.path}` as `{part_label}` on plate {part.plate} using filament {part.filament}."
            )

    lines.extend(
        [
            "",
            "## Finalize",
            "",
            f"1. Save the completed Bambu Studio project as `{spec.output_3mf}`.",
            "2. Reopen the saved .3mf and verify the part tree still shows the expected object/part split.",
            "3. Slice only after the grouped lid parts still expose separate filament assignments.",
        ]
    )

    if spec.notes:
        lines.extend(
            [
                "",
                "## Notes",
                "",
            ]
        )
        for note in spec.notes:
            lines.append(f"- {note}")

    return "\n".join(lines) + "\n"


def _format_nozzle(value: float) -> str:
    return f"{value:.1f}"


def _printer_label(target_printer: str) -> str:
    normalized = target_printer.strip().lower()
    aliases = {
        "a1": "A1",
        "bambu lab a1": "A1",
        "a1 mini": "A1 mini",
        "a1mini": "A1 mini",
        "bambu lab a1 mini": "A1 mini",
    }
    if normalized not in aliases:
        raise ValueError(f"Unsupported target_printer for preset resolution: {target_printer!r}")
    return aliases[normalized]


def bambu_support_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "BambuStudio" / "system" / "BBL"


def repo_hammerspoon_actions_path() -> Path:
    return Path(__file__).with_name("bambu_hammerspoon.lua").resolve()


def hammerspoon_init_path() -> Path:
    return Path.home() / ".hammerspoon" / "init.lua"


def _managed_hammerspoon_ipc_block() -> str:
    return (
        f"{HAMMERSPOON_INIT_MARKER_START}\n"
        'require("hs.ipc")\n'
        f"{HAMMERSPOON_INIT_MARKER_END}\n"
    )


def _init_contains_hammerspoon_ipc(text: str) -> bool:
    return (
        'require("hs.ipc")' in text
        or "require('hs.ipc')" in text
        or HAMMERSPOON_INIT_MARKER_START in text
    )


def _ensure_hammerspoon_ipc_init(init_path: str | Path | None = None) -> tuple[Path, bool, bool]:
    destination = Path(init_path or hammerspoon_init_path()).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    existed = destination.exists()
    current = destination.read_text() if existed else ""
    if _init_contains_hammerspoon_ipc(current):
        return destination.resolve(), existed, False

    block = _managed_hammerspoon_ipc_block()
    if current and not current.endswith("\n"):
        current += "\n"
    destination.write_text(current + block)
    return destination.resolve(), existed, True


def _resolve_hammerspoon_cli_path() -> Path | None:
    which_path = shutil.which("hs")
    if which_path:
        return Path(which_path)

    candidates = [
        Path("/opt/homebrew/bin/hs"),
        Path("/usr/local/bin/hs"),
        Path("/Applications/Hammerspoon.app/Contents/Resources/hs"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _probe_hammerspoon() -> tuple[str | None, bool, bool | None, str | None]:
    cli_path = _resolve_hammerspoon_cli_path()
    if cli_path is None:
        return None, False, None, None

    try:
        probe = subprocess.run(
            [str(cli_path), "-c", "return 1"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return str(cli_path), True, False, "Timed out waiting for Hammerspoon IPC"
    if probe.returncode == 0:
        return str(cli_path), True, True, None

    error = (probe.stderr or probe.stdout).strip() or "unknown hammerspoon error"
    return str(cli_path), True, False, error


def _probe_hammerspoon_accessibility_grant() -> tuple[bool | None, str | None]:
    database = Path.home() / "Library" / "Application Support" / "com.apple.TCC" / "TCC.db"
    if not database.exists():
        return None, f"TCC database not found at {database}"

    try:
        import sqlite3

        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        try:
            row = connection.execute(
                """
                select auth_value
                from access
                where service = 'kTCCServiceAccessibility'
                  and client = 'org.hammerspoon.Hammerspoon'
                order by last_modified desc
                limit 1
                """
            ).fetchone()
        finally:
            connection.close()
    except Exception as exc:
        return None, str(exc)

    if row is None:
        return False, None
    return bool(row[0]), None


def probe_bambu_studio(app_path: str | Path = "/Applications/BambuStudio.app") -> BambuStudioProbe:
    app = Path(app_path)
    executable = app / "Contents" / "MacOS" / "BambuStudio"
    support_dir = bambu_support_dir()
    version: str | None = None
    if app.exists():
        info_plist = app / "Contents" / "Info.plist"
        if info_plist.exists():
            with info_plist.open("rb") as handle:
                version = plistlib.load(handle).get("CFBundleShortVersionString")

    assistive_access: bool | None = None
    assistive_access_error: str | None = None
    if app.exists():
        probe = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to tell process "Finder" to get frontmost',
            ],
            capture_output=True,
            text=True,
        )
        if probe.returncode == 0:
            assistive_access = True
        else:
            assistive_access = False
            assistive_access_error = (probe.stderr or probe.stdout).strip() or "unknown osascript error"

    (
        hammerspoon_cli_path,
        hammerspoon_cli_available,
        hammerspoon_ipc_ready,
        hammerspoon_error,
    ) = _probe_hammerspoon()
    (
        hammerspoon_accessibility_granted,
        hammerspoon_accessibility_error,
    ) = _probe_hammerspoon_accessibility_grant()

    return BambuStudioProbe(
        installed=app.exists(),
        app_path=str(app),
        executable_path=str(executable),
        support_dir=str(support_dir),
        version=version,
        cli_available=executable.exists(),
        assistive_access=assistive_access,
        assistive_access_error=assistive_access_error,
        hammerspoon_cli_path=hammerspoon_cli_path,
        hammerspoon_cli_available=hammerspoon_cli_available,
        hammerspoon_ipc_ready=hammerspoon_ipc_ready,
        hammerspoon_error=hammerspoon_error,
        hammerspoon_accessibility_granted=hammerspoon_accessibility_granted,
        hammerspoon_accessibility_error=hammerspoon_accessibility_error,
    )


def expected_machine_profile_name(target_printer: str, nozzle_diameter: float) -> str:
    return f"Bambu Lab {_printer_label(target_printer)} {_format_nozzle(nozzle_diameter)} nozzle.json"


def expected_process_profile_name(target_printer: str, nozzle_diameter: float) -> str:
    printer = _printer_label(target_printer)
    layer_height = nozzle_diameter / 2
    base = f"{layer_height:.2f}mm Standard @BBL {printer}"
    if nozzle_diameter == 0.4:
        return f"{base}.json"
    return f"{base} {_format_nozzle(nozzle_diameter)} nozzle.json"


def expected_generic_pla_profile_name(target_printer: str, nozzle_diameter: float) -> str:
    printer = _printer_label(target_printer)
    base = f"Generic PLA @BBL {printer}"
    if nozzle_diameter == 0.4:
        return f"{base}.json"
    return f"{base} {_format_nozzle(nozzle_diameter)} nozzle.json"


def _resolve_profile_file(directory: Path, preferred: str, *, fallback_prefix: str | None = None) -> Path:
    candidate = directory / preferred
    if candidate.exists():
        return candidate
    if fallback_prefix is not None:
        matches = sorted(directory.glob(f"{fallback_prefix}*.json"))
        if matches:
            return matches[0]
    raise FileNotFoundError(f"Could not resolve Bambu profile {preferred!r} in {directory}")


def resolve_default_presets(
    target_printer: str,
    nozzle_diameter: float,
    filament_count: int,
    *,
    support_dir: str | Path | None = None,
) -> BambuPresetBundle:
    root = Path(support_dir) if support_dir is not None else bambu_support_dir()
    machine_dir = root / "machine"
    process_dir = root / "process"
    filament_dir = root / "filament"

    printer = _printer_label(target_printer)
    machine_path = _resolve_profile_file(
        machine_dir,
        expected_machine_profile_name(target_printer, nozzle_diameter),
        fallback_prefix=f"Bambu Lab {printer} {_format_nozzle(nozzle_diameter)} nozzle",
    )
    process_path = _resolve_profile_file(
        process_dir,
        expected_process_profile_name(target_printer, nozzle_diameter),
        fallback_prefix=f"{nozzle_diameter / 2:.2f}mm Standard @BBL {printer}",
    )
    filament_profile = _resolve_profile_file(
        filament_dir,
        expected_generic_pla_profile_name(target_printer, nozzle_diameter),
        fallback_prefix=f"Generic PLA @BBL {printer}",
    )

    return BambuPresetBundle(
        machine_path=str(machine_path),
        process_path=str(process_path),
        filament_paths=[str(filament_profile)] * filament_count,
    )


def resolve_cli_mesh_path(part: BambuPartSpec, *, require_existing: bool = True) -> Path:
    original = Path(part.path)
    if original.suffix.lower() in SUPPORTED_CLI_MESH_SUFFIXES:
        resolved = original
    else:
        resolved = original.with_suffix(".stl")
        if not resolved.exists() and require_existing:
            raise ValueError(
                f"Part {part.name!r} is {original.suffix or 'extensionless'}, but Bambu CLI assemble "
                "lists only accept STL/OBJ for multipart assembly and no STL fallback was found"
            )
    if require_existing and not resolved.exists():
        raise FileNotFoundError(f"Missing mesh file for part {part.name!r}: {resolved}")
    if resolved.suffix.lower() not in SUPPORTED_CLI_MESH_SUFFIXES:
        raise ValueError(f"Bambu CLI assemble list does not support {resolved.suffix!r} for part {part.name!r}")
    return resolved.resolve()


def resolve_gui_import_path(part: BambuPartSpec, *, require_existing: bool = True) -> Path:
    if part.load_strategy == "merge_as_parts":
        return resolve_cli_mesh_path(part, require_existing=require_existing)

    original = Path(part.path)
    if require_existing and not original.exists():
        raise FileNotFoundError(f"Missing import file for part {part.name!r}: {original}")
    return original.resolve()


def gui_import_name(part: BambuPartSpec) -> str:
    original = Path(part.path)
    if part.load_strategy == "merge_as_parts" and original.suffix.lower() not in SUPPORTED_CLI_MESH_SUFFIXES:
        return original.with_suffix(".stl").name
    return original.name


def build_gui_import_paths(spec: BambuProjectSpec) -> list[Path]:
    spec.validate()
    in_place_parts = [part for part in spec.parts if part.print_mode == "in_place_multicolor"]
    selected_parts = in_place_parts or spec.parts
    ordered_parts = sorted(
        selected_parts,
        key=lambda part: (part.plate, part.load_strategy, part.object_name or "", part.filament, part.name),
    )
    return [resolve_gui_import_path(part) for part in ordered_parts]


def build_gui_launch_command(
    spec: BambuProjectSpec,
    *,
    app_path: str | Path = DEFAULT_BAMBU_GUI_APP_PATH,
) -> list[str]:
    return ["open", "-a", str(Path(app_path)), *[str(path) for path in build_gui_import_paths(spec)]]


def _expand_values(values: Sequence[Any] | None, count: int, *, fill: Any) -> list[Any]:
    expanded = list(values or [])
    if not expanded:
        expanded = [fill]
    while len(expanded) < count:
        expanded.append(expanded[-1] if expanded else fill)
    return expanded[:count]


def _choose_palette_colors(count: int, *, existing: Sequence[str] | None = None) -> list[str]:
    colors = [color for color in (existing or []) if color]
    if not colors:
        colors = [DEFAULT_BAMBU_FILAMENT_COLORS[0]]
    palette = list(DEFAULT_BAMBU_FILAMENT_COLORS)
    while len(colors) < count:
        candidate = next((color for color in palette if color not in colors), DEFAULT_BAMBU_FILAMENT_COLORS[len(colors) % len(DEFAULT_BAMBU_FILAMENT_COLORS)])
        colors.append(candidate)
    return colors[:count]


def _dedupe_preserving_order(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _read_studio_config_3mf(input_3mf: Path) -> tuple[dict[str, Any], ET.Element]:
    with zipfile.ZipFile(input_3mf, "r") as archive:
        try:
            project_settings = json.loads(archive.read("Metadata/project_settings.config"))
            model_root = ET.fromstring(archive.read("Metadata/model_settings.config"))
        except KeyError as exc:
            raise ValueError(f"{input_3mf} is missing required Studio metadata: {exc.args[0]}") from exc
    return project_settings, model_root


def _rewrite_studio_3mf(
    input_3mf: Path,
    output_3mf: Path,
    project_settings: dict[str, Any],
    model_root: ET.Element,
) -> None:
    with tempfile.TemporaryDirectory(prefix="bambu_3mf_patch_") as tmpdir:
        extracted_dir = Path(tmpdir)
        with zipfile.ZipFile(input_3mf, "r") as archive:
            archive.extractall(extracted_dir)

        (extracted_dir / "Metadata" / "project_settings.config").write_text(
            json.dumps(project_settings, indent=4) + "\n"
        )
        ET.indent(model_root)
        ET.ElementTree(model_root).write(
            extracted_dir / "Metadata" / "model_settings.config",
            encoding="UTF-8",
            xml_declaration=True,
        )

        output_3mf.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_3mf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(extracted_dir.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(extracted_dir).as_posix())


def resolve_seed_template_3mf(
    spec: BambuProjectSpec,
    *,
    seed_template_3mf: str | Path | None = None,
    require_existing: bool = True,
) -> Path:
    spec.validate()
    candidate = Path(seed_template_3mf or spec.seed_template_3mf or "")
    if not candidate:
        raise ValueError("No seed_template_3mf was provided on the spec or override arguments")
    if candidate.suffix.lower() != ".3mf":
        raise ValueError(f"seed_template_3mf must end with '.3mf', got {candidate}")
    resolved = candidate.resolve()
    if require_existing and not resolved.exists():
        raise FileNotFoundError(f"Missing seed template 3MF: {resolved}")
    return resolved


def _expected_patchable_import_names(spec: BambuProjectSpec) -> dict[str, int]:
    expected_import_names: dict[str, int] = {}
    for part in spec.parts:
        if part.print_mode != "in_place_multicolor":
            continue
        expected_import_names[gui_import_name(part)] = part.filament
    return expected_import_names


def _studio_object_identity(obj: ET.Element) -> tuple[str, list[str]]:
    object_name = ""
    source_names: set[str] = set()
    for meta in obj.findall("metadata"):
        if meta.get("key") == "name":
            object_name = meta.get("value") or ""
    for part in obj.findall("part"):
        for meta in part.findall("metadata"):
            if meta.get("key") in {"source_file", "name"} and meta.get("value"):
                source_names.add(Path(meta.get("value")).name)
    return object_name, sorted(source_names)


def _match_patchable_studio_objects(
    model_root: ET.Element,
    expected_import_names: dict[str, int],
) -> list[tuple[ET.Element, str, str, list[str]]]:
    matched: list[tuple[ET.Element, str, str, list[str]]] = []
    for obj in model_root.findall("object"):
        object_name, source_names = _studio_object_identity(obj)
        matched_name = object_name if object_name in expected_import_names else None
        if matched_name is None:
            for candidate in source_names:
                if candidate in expected_import_names:
                    matched_name = candidate
                    break
        if matched_name is None:
            continue
        matched.append((obj, matched_name, object_name, source_names))
    return matched


def _part_identity(part: ET.Element) -> tuple[str, list[str]]:
    part_name = ""
    source_names: set[str] = set()
    for meta in part.findall("metadata"):
        if meta.get("key") == "name" and meta.get("value"):
            value = meta.get("value") or ""
            part_name = value
            source_names.add(Path(value).name)
        if meta.get("key") == "source_file" and meta.get("value"):
            source_names.add(Path(meta.get("value")).name)
    return part_name, sorted(source_names)


def check_seed_template_3mf(
    spec: BambuProjectSpec,
    *,
    seed_template_3mf: str | Path | None = None,
) -> BambuStudioTemplateCheckResult:
    spec.validate()
    expected_import_names = _expected_patchable_import_names(spec)
    expected_patchable_objects = sorted(expected_import_names)
    template_candidate = Path(seed_template_3mf or spec.seed_template_3mf or "")
    template_path = template_candidate.resolve() if template_candidate else template_candidate
    template_exists = bool(template_candidate) and template_path.exists()

    if not template_candidate:
        return BambuStudioTemplateCheckResult(
            template_3mf="",
            expected_patchable_objects=expected_patchable_objects,
            matched_patchable_objects=[],
            missing_patchable_objects=expected_patchable_objects,
            nozzle_count=0,
            template_exists=False,
            error_text="No seed_template_3mf was provided on the spec or override arguments",
        )

    if template_candidate.suffix.lower() != ".3mf":
        return BambuStudioTemplateCheckResult(
            template_3mf=str(template_path),
            expected_patchable_objects=expected_patchable_objects,
            matched_patchable_objects=[],
            missing_patchable_objects=expected_patchable_objects,
            nozzle_count=0,
            template_exists=template_exists,
            error_text=f"seed_template_3mf must end with '.3mf', got {template_candidate}",
        )

    if not template_exists:
        return BambuStudioTemplateCheckResult(
            template_3mf=str(template_path),
            expected_patchable_objects=expected_patchable_objects,
            matched_patchable_objects=[],
            missing_patchable_objects=expected_patchable_objects,
            nozzle_count=0,
            template_exists=False,
            error_text=f"Missing seed template 3MF: {template_path}",
        )

    try:
        project_settings, model_root = _read_studio_config_3mf(template_path)
    except Exception as exc:
        return BambuStudioTemplateCheckResult(
            template_3mf=str(template_path),
            expected_patchable_objects=expected_patchable_objects,
            matched_patchable_objects=[],
            missing_patchable_objects=expected_patchable_objects,
            nozzle_count=0,
            template_exists=True,
            error_text=str(exc),
        )

    nozzle_count = len(project_settings.get("nozzle_diameter", []))
    matched_names = _dedupe_preserving_order(
        [matched_name for _, matched_name, _, _ in _match_patchable_studio_objects(model_root, expected_import_names)]
    )
    missing_names = [name for name in expected_patchable_objects if name not in matched_names]
    notes: list[str] = []
    error_text: str | None = None
    if nozzle_count != 1:
        error_text = (
            "Seed template must be a single-nozzle Studio project for A1-style multicolor patching"
        )
    elif missing_names:
        error_text = "Seed template is missing expected patchable objects: " + ", ".join(missing_names)
    else:
        notes.append("Seed template contains all expected in-place multicolor objects.")

    return BambuStudioTemplateCheckResult(
        template_3mf=str(template_path),
        expected_patchable_objects=expected_patchable_objects,
        matched_patchable_objects=matched_names,
        missing_patchable_objects=missing_names,
        nozzle_count=nozzle_count,
        template_exists=True,
        error_text=error_text,
        notes=notes,
    )


def capture_seed_template_3mf(
    spec: BambuProjectSpec,
    input_3mf: str | Path,
    *,
    output_3mf: str | Path | None = None,
    overwrite: bool = False,
) -> BambuStudioTemplateCaptureResult:
    spec.validate()
    input_path = Path(input_3mf).resolve()
    template_check = check_seed_template_3mf(spec, seed_template_3mf=input_path)
    output_candidate = Path(output_3mf or spec.seed_template_3mf or "")

    if not output_candidate:
        return BambuStudioTemplateCaptureResult(
            input_3mf=str(input_path),
            output_3mf="",
            copied=False,
            overwrite=overwrite,
            output_exists=False,
            template_check=template_check,
            error_text="No output template path was provided and the spec does not define seed_template_3mf",
        )

    output_path = output_candidate.resolve()
    if output_path == input_path:
        return BambuStudioTemplateCaptureResult(
            input_3mf=str(input_path),
            output_3mf=str(output_path),
            copied=False,
            overwrite=overwrite,
            output_exists=output_path.exists(),
            template_check=template_check,
            error_text="Refusing to capture the seed template in place. Provide a different output path.",
        )

    if not template_check.success:
        return BambuStudioTemplateCaptureResult(
            input_3mf=str(input_path),
            output_3mf=str(output_path),
            copied=False,
            overwrite=overwrite,
            output_exists=output_path.exists(),
            template_check=template_check,
            error_text=template_check.error_text or "Template validation failed",
        )

    if output_path.exists() and not overwrite:
        return BambuStudioTemplateCaptureResult(
            input_3mf=str(input_path),
            output_3mf=str(output_path),
            copied=False,
            overwrite=overwrite,
            output_exists=True,
            template_check=template_check,
            error_text=f"Output template already exists: {output_path}",
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(input_path, output_path)
    return BambuStudioTemplateCaptureResult(
        input_3mf=str(input_path),
        output_3mf=str(output_path),
        copied=True,
        overwrite=overwrite,
        output_exists=output_path.exists(),
        template_check=template_check,
        notes=["Copied validated Studio-authored seed template into the project template path."],
    )


def _restart_hammerspoon_app(*, startup_timeout: float = 5.0) -> tuple[bool, list[str]]:
    notes: list[str] = []
    quit_process = subprocess.run(
        ["osascript", "-e", 'tell application "Hammerspoon" to quit'],
        capture_output=True,
        text=True,
    )
    if quit_process.returncode == 0:
        notes.append("Requested Hammerspoon restart via AppleScript.")
        time.sleep(1.0)

    open_process = subprocess.run(
        ["open", "-a", "Hammerspoon"],
        capture_output=True,
        text=True,
    )
    if open_process.returncode != 0:
        error = (open_process.stderr or open_process.stdout).strip() or "failed to launch Hammerspoon"
        notes.append(error)
        return False, notes

    deadline = time.monotonic() + startup_timeout
    last_error: str | None = None
    while time.monotonic() < deadline:
        _, available, ready, error = _probe_hammerspoon()
        if available and ready:
            return True, notes
        if error:
            last_error = error
        time.sleep(0.5)
    if last_error:
        notes.append(last_error)
    return False, notes


def setup_hammerspoon_for_bambu(
    *,
    app_path: str | Path = DEFAULT_BAMBU_GUI_APP_PATH,
    init_path: str | Path | None = None,
    restart: bool = True,
) -> BambuHammerspoonSetupResult:
    destination, existed, written = _ensure_hammerspoon_ipc_init(init_path)
    notes: list[str] = []
    if written:
        notes.append("Added hs.ipc bootstrap block to Hammerspoon init.lua.")
    else:
        notes.append("Hammerspoon init.lua already exposes hs.ipc or an existing managed block.")

    restart_succeeded = True
    if restart:
        restart_succeeded, restart_notes = _restart_hammerspoon_app()
        notes.extend(restart_notes)

    probe = probe_bambu_studio(app_path)
    error_text: str | None = None
    if not probe.hammerspoon_cli_available:
        error_text = "Hammerspoon CLI (hs) is not available after setup"
    elif probe.hammerspoon_ipc_ready is not True:
        detail = f": {probe.hammerspoon_error}" if probe.hammerspoon_error else ""
        error_text = f"Hammerspoon IPC is not ready after setup{detail}"
    elif restart and not restart_succeeded:
        error_text = "Hammerspoon restart failed during setup"

    return BambuHammerspoonSetupResult(
        init_path=str(destination),
        actions_path=str(repo_hammerspoon_actions_path()),
        init_existed=existed,
        init_written=written,
        restart_requested=restart,
        restart_succeeded=restart_succeeded,
        probe=probe,
        error_text=error_text,
        notes=notes,
    )


def patch_studio_3mf_multicolor(
    spec: BambuProjectSpec,
    input_3mf: str | Path,
    *,
    output_3mf: str | Path | None = None,
) -> BambuStudio3mfPatchResult:
    spec.validate()
    input_path = Path(input_3mf).resolve()
    output_path = Path(output_3mf or input_path).resolve()

    if spec.filament_count < 2:
        raise ValueError("patch_studio_3mf_multicolor requires at least two filaments")

    project_settings, model_root = _read_studio_config_3mf(input_path)
    nozzle_diameter = project_settings.get("nozzle_diameter", [])
    if len(nozzle_diameter) != 1:
        raise ValueError(
            "patch_studio_3mf_multicolor currently only supports single-nozzle Studio projects"
        )

    expected_import_names = _expected_patchable_import_names(spec)

    if not expected_import_names:
        raise ValueError("Bambu handoff spec does not describe any patchable Studio objects")

    patched_objects: list[str] = []
    matched_part_names: list[str] = []
    matched_objects = _match_patchable_studio_objects(model_root, expected_import_names)
    matched_names = _dedupe_preserving_order([matched_name for _, matched_name, _, _ in matched_objects])
    for obj, matched_name, object_name, source_names in matched_objects:
        matched_filament = expected_import_names[matched_name]

        extruder_meta = None
        for meta in obj.findall("metadata"):
            if meta.get("key") == "extruder":
                extruder_meta = meta
                break
        if extruder_meta is None:
            extruder_meta = ET.SubElement(obj, "metadata")
            extruder_meta.set("key", "extruder")
        extruder_meta.set("value", str(matched_filament))
        if object_name:
            patched_objects.append(object_name)
        elif source_names:
            patched_objects.append(sorted(source_names)[0])
        else:
            patched_objects.append(obj.get("id", ""))

    for obj in model_root.findall("object"):
        object_level_part_matches: list[tuple[ET.Element, str]] = []
        for part in obj.findall("part"):
            part_name, source_names = _part_identity(part)
            matched_part_name = None
            if part_name and Path(part_name).name in expected_import_names:
                matched_part_name = Path(part_name).name
            else:
                for candidate in source_names:
                    if candidate in expected_import_names:
                        matched_part_name = candidate
                        break
            if matched_part_name is None:
                continue
            object_level_part_matches.append((part, matched_part_name))

        if not object_level_part_matches:
            continue

        for part, matched_part_name in object_level_part_matches:
            matched_filament = expected_import_names[matched_part_name]
            extruder_meta = None
            for meta in part.findall("metadata"):
                if meta.get("key") == "extruder":
                    extruder_meta = meta
                    break
            if extruder_meta is None:
                extruder_meta = ET.SubElement(part, "metadata")
                extruder_meta.set("key", "extruder")
            extruder_meta.set("value", str(matched_filament))
            matched_part_names.append(matched_part_name)

        first_filament = expected_import_names[object_level_part_matches[0][1]]
        object_extruder_meta = None
        for meta in obj.findall("metadata"):
            if meta.get("key") == "extruder":
                object_extruder_meta = meta
                break
        if object_extruder_meta is None:
            object_extruder_meta = ET.SubElement(obj, "metadata")
            object_extruder_meta.set("key", "extruder")
        object_extruder_meta.set("value", str(first_filament))

        object_name, source_names = _studio_object_identity(obj)
        if object_name:
            patched_objects.append(object_name)
        elif source_names:
            patched_objects.append(sorted(source_names)[0])
        else:
            patched_objects.append(obj.get("id", ""))

    patched_objects = _dedupe_preserving_order(patched_objects)
    matched_part_names = _dedupe_preserving_order(matched_part_names)

    matched_targets = set(matched_names) | set(matched_part_names)
    if len(matched_targets) < len(expected_import_names):
        missing = sorted(set(expected_import_names) - matched_targets)
        raise ValueError(
            "Could not find imported Studio objects to patch for: " + ", ".join(missing)
        )

    filament_count = spec.filament_count
    existing_filament_colours = project_settings.get("filament_colour", [])
    filament_colours = _choose_palette_colors(filament_count, existing=existing_filament_colours)
    project_settings["filament_colour"] = filament_colours
    project_settings["filament_multi_colour"] = filament_colours.copy()
    project_settings["filament_colour_type"] = _expand_values(
        project_settings.get("filament_colour_type"), filament_count, fill="1"
    )
    project_settings["filament_ids"] = _expand_values(
        project_settings.get("filament_ids"), filament_count, fill="GFL99"
    )
    project_settings["filament_type"] = _expand_values(
        project_settings.get("filament_type"), filament_count, fill="PLA"
    )
    project_settings["filament_vendor"] = _expand_values(
        project_settings.get("filament_vendor"), filament_count, fill="Generic"
    )
    project_settings["filament_settings_id"] = _expand_values(
        project_settings.get("filament_settings_id"),
        filament_count,
        fill=f"Generic PLA @BBL {_printer_label(spec.target_printer)}",
    )
    project_settings["filament_extruder_variant"] = _expand_values(
        project_settings.get("filament_extruder_variant"),
        filament_count,
        fill="Direct Drive Standard",
    )
    project_settings["filament_self_index"] = [str(index) for index in range(1, filament_count + 1)]
    project_settings["filament_map"] = ["1"] * filament_count
    project_settings["filament_nozzle_map"] = ["0"] * filament_count
    project_settings["filament_volume_map"] = ["0"] * filament_count
    project_settings["filament_adhesiveness_category"] = _expand_values(
        project_settings.get("filament_adhesiveness_category"), filament_count, fill="100"
    )
    project_settings["filament_prime_volume"] = _expand_values(
        project_settings.get("filament_prime_volume"), filament_count, fill="45"
    )
    project_settings["flush_volumes_vector"] = _expand_values(
        project_settings.get("flush_volumes_vector"), filament_count, fill="140"
    )
    project_settings.setdefault("filament_map_mode", "Auto For Flush")

    if "flush_volumes_matrix" not in project_settings or len(project_settings["flush_volumes_matrix"]) != filament_count**2:
        project_settings["flush_volumes_matrix"] = [
            "0" if row == col else "140"
            for row in range(filament_count)
            for col in range(filament_count)
        ]

    _rewrite_studio_3mf(input_path, output_path, project_settings, model_root)

    return BambuStudio3mfPatchResult(
        input_3mf=str(input_path),
        output_3mf=str(output_path),
        filament_count=filament_count,
        nozzle_count=1,
        patched_objects=patched_objects,
        output_exists=output_path.exists(),
        patched=True,
        notes=[
            "Patched Studio-authored project settings for multicolor filament slots.",
            "Single-nozzle A1-style projects keep physical nozzle arrays unchanged.",
        ],
    )


def apply_seed_template_3mf(
    spec: BambuProjectSpec,
    *,
    output_3mf: str | Path | None = None,
    seed_template_3mf: str | Path | None = None,
) -> BambuStudio3mfPatchResult:
    template_path = resolve_seed_template_3mf(spec, seed_template_3mf=seed_template_3mf)
    output_path = Path(output_3mf or spec.output_3mf).resolve()
    if output_path == template_path:
        raise ValueError(
            "Refusing to patch the seed template in place. Provide a different output_3mf."
        )
    template_check = check_seed_template_3mf(spec, seed_template_3mf=template_path)
    if not template_check.success:
        raise ValueError(template_check.error_text or "Seed template validation failed")

    result = patch_studio_3mf_multicolor(spec, template_path, output_3mf=output_path)
    return BambuStudio3mfPatchResult(
        input_3mf=result.input_3mf,
        output_3mf=result.output_3mf,
        filament_count=result.filament_count,
        nozzle_count=result.nozzle_count,
        patched_objects=result.patched_objects,
        output_exists=result.output_exists,
        patched=result.patched,
        error_text=result.error_text,
        notes=[
            f"Patched from seed template: {template_path}",
            f"Validated seed template objects: {', '.join(template_check.matched_patchable_objects)}",
            *result.notes,
        ],
    )


def _should_normalize_gui_output_with_seed_template(spec: BambuProjectSpec) -> bool:
    return bool(spec.seed_template_3mf) and any(
        part.print_mode == "in_place_multicolor" for part in spec.parts
    )


def _export_seed_template_as_gui_result(
    spec: BambuProjectSpec,
    *,
    output_3mf: str | Path | None = None,
) -> BambuGuiExportResult:
    output_path = Path(output_3mf or spec.output_3mf).resolve()
    try:
        template_result = apply_seed_template_3mf(spec, output_3mf=output_path)
    except Exception as exc:
        return BambuGuiExportResult(
            command=[],
            output_3mf=str(output_path),
            import_paths=[],
            launch_returncode=None,
            stdout="",
            stderr="",
            output_exists=output_path.exists(),
            merge_dialog_clicked=False,
            save_panel_handled=False,
            click_backend_used="seed_template",
            error_text=str(exc),
            notes=[
                "Configured seed template takes precedence over grouped GUI import for this project.",
            ],
        )

    return BambuGuiExportResult(
        command=[],
        output_3mf=template_result.output_3mf,
        import_paths=[],
        launch_returncode=0,
        stdout="",
        stderr="",
        output_exists=template_result.output_exists,
        merge_dialog_clicked=False,
        save_panel_handled=False,
        click_backend_used="seed_template",
        error_text=template_result.error_text,
        notes=[
            "Configured seed template takes precedence over grouped GUI import for this project.",
            *template_result.notes,
        ],
    )


def build_cli_assemble_payload(spec: BambuProjectSpec) -> dict[str, Any]:
    spec.validate()
    grouped_indices: dict[tuple[int, str], int] = {}
    top_level_counts: dict[int, int] = defaultdict(int)
    plates: dict[int, list[dict[str, Any]]] = defaultdict(list)
    next_assemble_index = 1

    ordered_parts = sorted(
        spec.parts,
        key=lambda part: (part.plate, part.load_strategy, part.object_name or "", part.filament, part.name),
    )

    for part in ordered_parts:
        cli_path = resolve_cli_mesh_path(part)
        object_payload: dict[str, Any] = {
            "path": str(cli_path),
            "count": 1,
            "filaments": [part.filament],
            "pos_x": [0.0],
            "pos_y": [0.0],
            "pos_z": [0.0],
        }
        if part.load_strategy == "merge_as_parts":
            group_key = (part.plate, part.object_name or "")
            if group_key not in grouped_indices:
                grouped_indices[group_key] = next_assemble_index
                next_assemble_index += 1
                top_level_counts[part.plate] += 1
            object_payload["assemble_index"] = [grouped_indices[group_key]]
        else:
            top_level_counts[part.plate] += 1
        plates[part.plate].append(object_payload)

    payload = {"plates": []}
    for plate_number in sorted(plates):
        payload["plates"].append(
            {
                "plate_name": f"Plate {plate_number}",
                "need_arrange": top_level_counts[plate_number] > 1,
                "objects": plates[plate_number],
            }
        )
    return payload


def write_cli_assemble_list(spec: BambuProjectSpec, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(build_cli_assemble_payload(spec), indent=2) + "\n")
    return destination


def _find_latest_bambu_crash_report(since_epoch: float) -> Path | None:
    crash_dir = Path.home() / "Library" / "Logs" / "DiagnosticReports"
    matches = [
        candidate
        for candidate in crash_dir.glob("BambuStudio-*.ips")
        if candidate.stat().st_mtime >= since_epoch
    ]
    if not matches:
        return None
    return max(matches, key=lambda candidate: candidate.stat().st_mtime)


def export_3mf_with_bambu_cli(
    spec: BambuProjectSpec,
    *,
    output_3mf: str | Path | None = None,
    assemble_list_path: str | Path | None = None,
    support_dir: str | Path | None = None,
) -> BambuCliExportResult:
    probe = probe_bambu_studio()
    if not probe.installed or not probe.cli_available:
        raise RuntimeError("Bambu Studio CLI is not available on this machine")

    presets = resolve_default_presets(
        spec.target_printer,
        spec.nozzle_diameter,
        spec.filament_count,
        support_dir=support_dir or probe.support_dir,
    )
    output = Path(output_3mf or spec.output_3mf).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    if assemble_list_path is None:
        temp_handle = tempfile.NamedTemporaryFile(prefix="bambu_assemble_", suffix=".json", delete=False)
        temp_handle.close()
        assemble_path = write_cli_assemble_list(spec, temp_handle.name)
    else:
        assemble_path = write_cli_assemble_list(spec, assemble_list_path)

    command = [
        probe.executable_path,
        "--load-assemble-list",
        str(assemble_path),
        "--load-settings",
        f"{presets.machine_path};{presets.process_path}",
        "--load-filaments",
        ";".join(presets.filament_paths),
        "--load-defaultfila",
        "--export-3mf",
        str(output),
        "--outputdir",
        str(output.parent),
    ]
    if spec.filament_count > 1:
        command.append("--allow-multicolor-oneplate")

    before = time.time()
    process = subprocess.run(command, capture_output=True, text=True)
    crash_report = _find_latest_bambu_crash_report(before)

    return BambuCliExportResult(
        command=command,
        output_3mf=str(output),
        assemble_list_path=str(assemble_path),
        presets=presets,
        returncode=process.returncode,
        stdout=process.stdout,
        stderr=process.stderr,
        output_exists=output.exists(),
        crash_report=str(crash_report) if crash_report else None,
    )


def _run_osascript(script: str, *, timeout: float = 10.0) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stderr = (exc.stderr or exc.stdout or "").strip()
        if stderr:
            stderr = f"{stderr}\n"
        stderr += f"osascript timed out after {timeout:.1f}s"
        return subprocess.CompletedProcess(
            ["osascript", "-e", script],
            124,
            exc.stdout or "",
            stderr,
        )


def _escape_applescript_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _bambu_window_names() -> list[str]:
    script = """
tell application "System Events"
  if not (exists process "BambuStudio") then return ""
  tell process "BambuStudio"
    if not (exists window 1) then return ""
    return name of every window as text
  end tell
end tell
"""
    result = _run_osascript(script)
    if result.returncode != 0:
        return []
    text = result.stdout.strip()
    if not text:
        return []
    return [item.strip() for item in text.split(",") if item.strip()]


def _wait_for_bambu_windows(predicate, *, timeout: float) -> list[str]:
    deadline = time.monotonic() + timeout
    last_names: list[str] = []
    while time.monotonic() < deadline:
        names = _bambu_window_names()
        last_names = names
        if predicate(names):
            return names
        time.sleep(0.25)
    return last_names


def _has_unsaved_bambu_project_alert(window_names: list[str]) -> bool:
    return any(name.startswith("Bambu Studio - Save") for name in window_names)


def _has_restore_bambu_project_prompt(window_names: list[str]) -> bool:
    return any(name.startswith("Bambu Studio - Restore") for name in window_names)


def _has_bambu_merge_prompt(window_names: list[str]) -> bool:
    return any("Object with multiple parts was detected" in name for name in window_names)


def _has_bambu_loading_window(window_names: list[str]) -> bool:
    return any("Loading..." in name for name in window_names)


def _has_bambu_project_window(window_names: list[str]) -> bool:
    ignored_prefixes = (
        "Object with multiple parts was detected",
        "Loading...",
        "Bambu Studio - Save",
        "Bambu Studio - Restore",
        "Save",
    )
    return any(name and not name.startswith(ignored_prefixes) for name in window_names)


def _bambu_import_ready(window_names: list[str], *, needs_merge_confirmation: bool, merge_dialog_clicked: bool) -> bool:
    if needs_merge_confirmation and not merge_dialog_clicked:
        return False
    if _has_bambu_merge_prompt(window_names):
        return False
    if _has_bambu_loading_window(window_names):
        return False
    return _has_bambu_project_window(window_names)


def _dismiss_bambu_restore_prompt() -> subprocess.CompletedProcess[str]:
    script = """
tell application "System Events"
  if exists process "BambuStudio" then
    tell process "BambuStudio"
      key code 53
    end tell
  end if
end tell
"""
    return _run_osascript(script)


def _dismiss_bambu_unsaved_changes_dialog() -> subprocess.CompletedProcess[str]:
    script = """
tell application "System Events"
  if exists process "BambuStudio" then
    tell process "BambuStudio"
      set frontmost to true
      key code 53
    end tell
  end if
end tell
"""
    return _run_osascript(script)


def _dismiss_bambu_save_panel() -> subprocess.CompletedProcess[str]:
    script = """
tell application "System Events"
  if exists process "BambuStudio" then
    tell process "BambuStudio"
      if exists window "Save" then
        click button "Cancel" of splitter group 1 of window "Save"
      end if
    end tell
  end if
end tell
"""
    return _run_osascript(script)


def _recover_bambu_gui_state(*, timeout: float = 5.0) -> list[str]:
    deadline = time.monotonic() + timeout
    last_names: list[str] = []
    while time.monotonic() < deadline:
        names = _bambu_window_names()
        last_names = names
        changed = False
        if _has_restore_bambu_project_prompt(names):
            _dismiss_bambu_restore_prompt()
            changed = True
        if _has_unsaved_bambu_project_alert(names):
            _dismiss_bambu_unsaved_changes_dialog()
            changed = True
        if "Save" in names:
            _dismiss_bambu_save_panel()
            changed = True
        if not changed:
            return names
        time.sleep(0.5)
    return last_names


def _bring_bambu_to_front() -> subprocess.CompletedProcess[str]:
    script = """
tell application "System Events"
  if exists process "BambuStudio" then
    tell process "BambuStudio"
      set frontmost to true
    end tell
  end if
end tell
"""
    return _run_osascript(script)


def _bambu_process_exists() -> bool:
    script = """
tell application "System Events"
  return exists process "BambuStudio"
end tell
"""
    result = _run_osascript(script)
    return result.returncode == 0 and result.stdout.strip().lower() == "true"


def _quit_bambu_application() -> subprocess.CompletedProcess[str]:
    script = """
tell application id "com.bambulab.bambu-studio"
  quit
end tell
"""
    return _run_osascript(script)


def _wait_for_bambu_process_exit(*, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _bambu_process_exists():
            return True
        time.sleep(0.25)
    return not _bambu_process_exists()


def _click_screen_point(x: int, y: int) -> tuple[int, str, str]:
    helper_source = f"""
import CoreGraphics
import Foundation

let point = CGPoint(x: {x}, y: {y})
let source = CGEventSource(stateID: .hidSystemState)
let move = CGEvent(mouseEventSource: source, mouseType: .mouseMoved, mouseCursorPosition: point, mouseButton: .left)
let down = CGEvent(mouseEventSource: source, mouseType: .leftMouseDown, mouseCursorPosition: point, mouseButton: .left)
let up = CGEvent(mouseEventSource: source, mouseType: .leftMouseUp, mouseCursorPosition: point, mouseButton: .left)
move?.post(tap: .cghidEventTap)
down?.post(tap: .cghidEventTap)
up?.post(tap: .cghidEventTap)
"""
    click_process = subprocess.run(["swift", "-e", helper_source], capture_output=True, text=True)
    return click_process.returncode, click_process.stdout, click_process.stderr


def _escape_lua_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _run_hammerspoon_action(
    action_name: str,
    *,
    cli_path: str | Path,
    args: Sequence[Any] = (),
    timeout: float = 5.0,
) -> tuple[int, str, str]:
    bundle_path = _escape_lua_string(str(repo_hammerspoon_actions_path()))
    encoded_args = ", ".join(json.dumps(arg) for arg in args)
    helper_source = (
        f'local actions = dofile("{bundle_path}")\n'
        'local hsjson = require("hs.json")\n'
        f'local result = actions.{action_name}({encoded_args})\n'
        'print(hsjson.encode(result))\n'
    )
    try:
        action_process = subprocess.run(
            [str(cli_path), "-c", helper_source],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout or "", exc.stderr or "Timed out waiting for Hammerspoon action"
    return action_process.returncode, action_process.stdout, action_process.stderr


def _click_screen_point_hammerspoon(
    x: int,
    y: int,
    *,
    cli_path: str | Path,
) -> tuple[int, str, str]:
    return _run_hammerspoon_action(
        "bambu_click_merge_confirm",
        cli_path=cli_path,
        args=(x, y),
    )


def _resolve_gui_click_backend(
    requested_backend: str,
    probe: BambuStudioProbe,
) -> str:
    if requested_backend not in SUPPORTED_GUI_CLICK_BACKENDS:
        raise ValueError(
            f"click_backend must be one of {sorted(SUPPORTED_GUI_CLICK_BACKENDS)}, got {requested_backend!r}"
        )
    if requested_backend == "auto":
        if probe.hammerspoon_cli_available and probe.hammerspoon_ipc_ready:
            return "hammerspoon"
        return "swift"
    if requested_backend == "hammerspoon":
        if not probe.hammerspoon_cli_available:
            raise RuntimeError("Hammerspoon CLI (hs) is not available on this machine")
        if probe.hammerspoon_ipc_ready is False:
            detail = f": {probe.hammerspoon_error}" if probe.hammerspoon_error else ""
            raise RuntimeError(f"Hammerspoon CLI is present but not ready{detail}")
    return requested_backend


def _click_screen_point_with_backend(
    x: int,
    y: int,
    *,
    requested_backend: str,
    probe: BambuStudioProbe,
) -> tuple[str, int, str, str]:
    attempted_errors: list[str] = []
    if requested_backend == "auto" and probe.hammerspoon_cli_available and probe.hammerspoon_ipc_ready:
        click_returncode, click_stdout, click_stderr = _click_screen_point_hammerspoon(
            x,
            y,
            cli_path=probe.hammerspoon_cli_path or "hs",
        )
        if click_returncode == 0:
            return "hammerspoon", click_returncode, click_stdout, click_stderr
        attempted_errors.append(click_stderr.strip() or click_stdout.strip() or "hammerspoon click failed")

    backend = "swift" if attempted_errors and requested_backend == "auto" else _resolve_gui_click_backend(requested_backend, probe)
    if backend == "hammerspoon":
        click_returncode, click_stdout, click_stderr = _click_screen_point_hammerspoon(
            x,
            y,
            cli_path=probe.hammerspoon_cli_path or "hs",
        )
    else:
        click_returncode, click_stdout, click_stderr = _click_screen_point(x, y)

    if attempted_errors:
        click_stderr = "\n".join(filter(None, [*attempted_errors, click_stderr.strip()]))
    return backend, click_returncode, click_stdout, click_stderr


def _open_bambu_save_project_as() -> subprocess.CompletedProcess[str]:
    script = """
tell application "System Events"
  if exists process "BambuStudio" then
    tell process "BambuStudio"
      set frontmost to true
      click menu item "Save Project as..." of menu "File" of menu bar 1
    end tell
  end if
end tell
"""
    return _run_osascript(script)


def _save_bambu_project_to_path(output_path: Path, *, save_timeout: float = 30.0) -> tuple[bool, str]:
    menu_result = _open_bambu_save_project_as()
    if menu_result.returncode != 0:
        stderr = menu_result.stderr or menu_result.stdout
        if stderr:
            return False, stderr.strip()
    time.sleep(min(1.5, save_timeout))

    directory = _escape_applescript_string(str(output_path.parent))
    filename = _escape_applescript_string(output_path.name)
    script = f"""
tell application "System Events"
  if exists process "BambuStudio" then
    tell process "BambuStudio"
      set frontmost to true
      if not (exists window "Save") then error "Save window not visible"
      keystroke "g" using {{command down, shift down}}
      delay 0.5
      if not (exists sheet 1 of window "Save") then error "Go to the folder sheet not visible"
      tell sheet 1 of window "Save"
        click text field 1
        keystroke "a" using {{command down}}
        keystroke "{directory}"
        key code 36
      end tell
      delay 0.75
      click text field 1 of splitter group 1 of window "Save"
      keystroke "a" using {{command down}}
      keystroke "{filename}"
      click button "Save" of splitter group 1 of window "Save"
    end tell
  end if
end tell
"""
    save_result = _run_osascript(script)
    if save_result.returncode != 0:
        return False, (save_result.stderr or save_result.stdout or "failed to confirm Save Project as...")

    return True, ""


def _confirm_bambu_merge_prompt(
    merge_click: tuple[int, int],
    *,
    click_backend: str = DEFAULT_BAMBU_GUI_CLICK_BACKEND,
    probe: BambuStudioProbe,
    timeout: float = 5.0,
) -> tuple[bool, str | None, str | None, str]:
    _bring_bambu_to_front()
    time.sleep(0.25)
    used_backend, click_returncode, click_stdout, click_stderr = _click_screen_point_with_backend(
        *merge_click,
        requested_backend=click_backend,
        probe=probe,
    )
    if click_returncode != 0:
        return False, click_stdout.strip() or None, click_stderr.strip() or None, used_backend
    remaining = _wait_for_bambu_windows(
        lambda names: not _has_bambu_merge_prompt(names),
        timeout=timeout,
    )
    return (
        not _has_bambu_merge_prompt(remaining),
        click_stdout.strip() or None,
        click_stderr.strip() or None,
        used_backend,
    )


def export_3mf_with_bambu_gui(
    spec: BambuProjectSpec,
    *,
    output_3mf: str | Path | None = None,
    app_path: str | Path = DEFAULT_BAMBU_GUI_APP_PATH,
    merge_click: tuple[int, int] = DEFAULT_BAMBU_GUI_MERGE_CLICK,
    click_backend: str = DEFAULT_BAMBU_GUI_CLICK_BACKEND,
    import_timeout: float = 30.0,
    save_timeout: float = 30.0,
) -> BambuGuiExportResult:
    output = Path(output_3mf or spec.output_3mf).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    if _should_normalize_gui_output_with_seed_template(spec):
        return _export_seed_template_as_gui_result(spec, output_3mf=output)

    probe = probe_bambu_studio(app_path)

    current_windows = _recover_bambu_gui_state()
    if _has_unsaved_bambu_project_alert(current_windows):
        return BambuGuiExportResult(
            command=[],
            output_3mf=str(output),
            import_paths=[],
            launch_returncode=None,
            stdout="",
            stderr="",
            output_exists=output.exists(),
            merge_dialog_clicked=False,
            save_panel_handled=False,
            click_backend_used=None,
            error_text=(
                "Bambu Studio already has an unsaved-changes dialog open. "
                "Close or save the current project before running the GUI exporter."
            ),
            notes=[],
        )
    if _has_restore_bambu_project_prompt(current_windows):
        _dismiss_bambu_restore_prompt()

    try:
        import_paths = build_gui_import_paths(spec)
    except Exception as exc:
        return BambuGuiExportResult(
            command=[],
            output_3mf=str(output),
            import_paths=[],
            launch_returncode=None,
            stdout="",
            stderr="",
            output_exists=output.exists(),
            merge_dialog_clicked=False,
            save_panel_handled=False,
            click_backend_used=None,
            error_text=str(exc),
            notes=[],
        )

    if not probe.installed:
        return BambuGuiExportResult(
            command=[],
            output_3mf=str(output),
            import_paths=[str(path) for path in import_paths],
            launch_returncode=None,
            stdout="",
            stderr="",
            output_exists=output.exists(),
            merge_dialog_clicked=False,
            save_panel_handled=False,
            click_backend_used=None,
            error_text="Bambu Studio is not installed at the requested app path",
            notes=[],
        )

    if current_windows or _bambu_process_exists():
        quit_result = _quit_bambu_application()
        quit_error = (quit_result.stderr or quit_result.stdout).strip()
        if quit_result.returncode != 0 and quit_error:
            return BambuGuiExportResult(
                command=[],
                output_3mf=str(output),
                import_paths=[str(path) for path in import_paths],
                launch_returncode=None,
                stdout="",
                stderr=quit_error,
                output_exists=output.exists(),
                merge_dialog_clicked=False,
                save_panel_handled=False,
                click_backend_used=None,
                error_text="Failed to reset Bambu Studio to a clean process state before import",
                notes=[],
            )
        if not _wait_for_bambu_process_exit():
            return BambuGuiExportResult(
                command=[],
                output_3mf=str(output),
                import_paths=[str(path) for path in import_paths],
                launch_returncode=None,
                stdout="",
                stderr="",
                output_exists=output.exists(),
                merge_dialog_clicked=False,
                save_panel_handled=False,
                click_backend_used=None,
                error_text="Bambu Studio did not exit cleanly before the GUI export relaunch",
                notes=[],
            )

    try:
        selected_click_backend = _resolve_gui_click_backend(click_backend, probe)
    except Exception as exc:
        return BambuGuiExportResult(
            command=[],
            output_3mf=str(output),
            import_paths=[str(path) for path in import_paths],
            launch_returncode=None,
            stdout="",
            stderr="",
            output_exists=output.exists(),
            merge_dialog_clicked=False,
            save_panel_handled=False,
            click_backend_used=None,
            error_text=str(exc),
            notes=[],
        )

    command = build_gui_launch_command(spec, app_path=probe.app_path)
    launch_process = subprocess.run(command, capture_output=True, text=True)
    stdout_chunks = [launch_process.stdout.strip()]
    stderr_chunks = [launch_process.stderr.strip()]
    notes = [
        "This GUI path is calibrated to the local macOS import/save flow.",
        "Bambu Studio is relaunched into a clean process state before grouped imports.",
        f"Multipart merge confirmation uses the {selected_click_backend} click backend.",
    ]
    if any(part.print_mode == "in_place_multicolor" for part in spec.parts):
        notes.append(
            "GUI export currently targets the grouped in-place multicolor object only; "
            "side-by-side accents and separate base parts stay outside this saved project."
        )
    needs_merge_confirmation = any(part.load_strategy == "merge_as_parts" for part in spec.parts)

    if launch_process.returncode != 0:
        return BambuGuiExportResult(
            command=command,
            output_3mf=str(output),
            import_paths=[str(path) for path in import_paths],
            launch_returncode=launch_process.returncode,
            stdout="\n".join(chunk for chunk in stdout_chunks if chunk),
            stderr="\n".join(chunk for chunk in stderr_chunks if chunk),
            output_exists=output.exists(),
            merge_dialog_clicked=False,
            save_panel_handled=False,
            click_backend_used=selected_click_backend,
            error_text="Bambu Studio import launch failed",
            notes=notes,
        )

    _bring_bambu_to_front()
    merge_dialog_clicked = False
    save_panel_handled = False
    click_backend_used = selected_click_backend
    error_text: str | None = None

    def _current_names() -> list[str]:
        return _bambu_window_names()

    try:
        deadline = time.monotonic() + import_timeout
        while time.monotonic() < deadline:
            names = _current_names()
            if _has_unsaved_bambu_project_alert(names):
                _dismiss_bambu_unsaved_changes_dialog()
                time.sleep(0.5)
                continue
            if _has_restore_bambu_project_prompt(names):
                _dismiss_bambu_restore_prompt()
                time.sleep(0.5)
                continue
            if _has_bambu_merge_prompt(names) and not merge_dialog_clicked:
                (
                    merge_dialog_clicked,
                    click_stdout,
                    click_stderr,
                    click_backend_used,
                ) = _confirm_bambu_merge_prompt(
                    merge_click,
                    click_backend=click_backend,
                    probe=probe,
                    timeout=min(5.0, import_timeout),
                )
                if click_stdout:
                    stdout_chunks.append(click_stdout)
                if click_stderr:
                    stderr_chunks.append(click_stderr)
                if not merge_dialog_clicked:
                    error_text = "Failed to accept the multipart merge dialog"
                    break
                continue
            if _bambu_import_ready(
                names,
                needs_merge_confirmation=needs_merge_confirmation,
                merge_dialog_clicked=merge_dialog_clicked,
            ):
                break
            time.sleep(0.25)

        current_names = _current_names()
        if error_text is None and not _bambu_import_ready(
            current_names,
            needs_merge_confirmation=needs_merge_confirmation,
            merge_dialog_clicked=merge_dialog_clicked,
        ):
            error_text = "Bambu Studio did not finish importing the project"

        if error_text is None:
            _recover_bambu_gui_state(timeout=min(5.0, save_timeout))
            save_panel_handled, save_error = _save_bambu_project_to_path(output, save_timeout=save_timeout)
            if not save_panel_handled:
                error_text = save_error

        if error_text is None:
            deadline = time.monotonic() + save_timeout
            while time.monotonic() < deadline and not output.exists():
                time.sleep(0.25)
            if not output.exists():
                error_text = f"Bambu Studio did not write the expected .3mf at {output}"
            elif spec.filament_count > 1:
                patch_result = patch_studio_3mf_multicolor(spec, output, output_3mf=output)
                patched_objects = list(dict.fromkeys(patch_result.patched_objects))
                notes.extend(
                    [
                        f"Patched Studio project for {patch_result.filament_count} filament slots.",
                        f"Patched imported objects: {', '.join(patched_objects)}",
                    ]
                )
    except Exception as exc:
        error_text = str(exc)

    return BambuGuiExportResult(
        command=command,
        output_3mf=str(output),
        import_paths=[str(path) for path in import_paths],
        launch_returncode=launch_process.returncode,
        stdout="\n".join(chunk for chunk in stdout_chunks if chunk),
        stderr="\n".join(chunk for chunk in stderr_chunks if chunk),
        output_exists=output.exists(),
        merge_dialog_clicked=merge_dialog_clicked,
        save_panel_handled=save_panel_handled,
        click_backend_used=click_backend_used,
        error_text=error_text,
        notes=notes,
    )


def format_bambu_probe(probe: BambuStudioProbe) -> str:
    lines = [
        f"installed={probe.installed}",
        f"cli_available={probe.cli_available}",
        f"version={probe.version or 'unknown'}",
        f"app_path={probe.app_path}",
        f"executable_path={probe.executable_path}",
        f"support_dir={probe.support_dir}",
        f"assistive_access={probe.assistive_access}",
        f"hammerspoon_cli_available={probe.hammerspoon_cli_available}",
        f"hammerspoon_ipc_ready={probe.hammerspoon_ipc_ready}",
        f"hammerspoon_accessibility_granted={probe.hammerspoon_accessibility_granted}",
    ]
    if probe.assistive_access_error:
        lines.append(f"assistive_access_error={probe.assistive_access_error}")
    if probe.hammerspoon_cli_path:
        lines.append(f"hammerspoon_cli_path={probe.hammerspoon_cli_path}")
    if probe.hammerspoon_error:
        lines.append(f"hammerspoon_error={probe.hammerspoon_error}")
    if probe.hammerspoon_accessibility_error:
        lines.append(f"hammerspoon_accessibility_error={probe.hammerspoon_accessibility_error}")
    return "\n".join(lines) + "\n"


def format_bambu_cli_export_result(result: BambuCliExportResult) -> str:
    lines = [
        f"success={result.success}",
        f"returncode={result.returncode}",
        f"output_exists={result.output_exists}",
        f"output_3mf={result.output_3mf}",
        f"assemble_list_path={result.assemble_list_path}",
        f"machine_preset={result.presets.machine_path}",
        f"process_preset={result.presets.process_path}",
        f"filament_presets={';'.join(result.presets.filament_paths)}",
        "command=" + " ".join(result.command),
    ]
    if result.crash_report:
        lines.append(f"crash_report={result.crash_report}")
    stdout_tail = result.stdout.strip().splitlines()[-10:]
    if stdout_tail:
        lines.append("stdout_tail:")
        lines.extend(stdout_tail)
    stderr_tail = result.stderr.strip().splitlines()[-10:]
    if stderr_tail:
        lines.append("stderr_tail:")
        lines.extend(stderr_tail)
    return "\n".join(lines) + "\n"


def format_bambu_gui_export_result(result: BambuGuiExportResult) -> str:
    lines = [
        f"success={result.success}",
        f"launch_returncode={result.launch_returncode}",
        f"output_exists={result.output_exists}",
        f"output_3mf={result.output_3mf}",
        f"merge_dialog_clicked={result.merge_dialog_clicked}",
        f"save_panel_handled={result.save_panel_handled}",
        f"click_backend_used={result.click_backend_used}",
        f"import_paths={';'.join(result.import_paths)}",
        "command=" + " ".join(result.command),
    ]
    if result.error_text:
        lines.append(f"error_text={result.error_text}")
    if result.notes:
        lines.append("notes:")
        lines.extend(f"- {note}" for note in result.notes)
    stdout_tail = result.stdout.strip().splitlines()[-10:]
    if stdout_tail:
        lines.append("stdout_tail:")
        lines.extend(stdout_tail)
    stderr_tail = result.stderr.strip().splitlines()[-10:]
    if stderr_tail:
        lines.append("stderr_tail:")
        lines.extend(stderr_tail)
    return "\n".join(lines) + "\n"


def format_bambu_patch_result(result: BambuStudio3mfPatchResult) -> str:
    lines = [
        f"success={result.success}",
        f"patched={result.patched}",
        f"filament_count={result.filament_count}",
        f"nozzle_count={result.nozzle_count}",
        f"output_exists={result.output_exists}",
        f"input_3mf={result.input_3mf}",
        f"output_3mf={result.output_3mf}",
        f"patched_objects={';'.join(result.patched_objects)}",
    ]
    if result.error_text:
        lines.append(f"error_text={result.error_text}")
    if result.notes:
        lines.append("notes:")
        lines.extend(f"- {note}" for note in result.notes)
    return "\n".join(lines) + "\n"


def format_bambu_template_check_result(result: BambuStudioTemplateCheckResult) -> str:
    lines = [
        f"success={result.success}",
        f"template_exists={result.template_exists}",
        f"template_3mf={result.template_3mf}",
        f"nozzle_count={result.nozzle_count}",
        f"expected_patchable_objects={';'.join(result.expected_patchable_objects)}",
        f"matched_patchable_objects={';'.join(result.matched_patchable_objects)}",
        f"missing_patchable_objects={';'.join(result.missing_patchable_objects)}",
    ]
    if result.error_text:
        lines.append(f"error_text={result.error_text}")
    if result.notes:
        lines.append("notes:")
        lines.extend(f"- {note}" for note in result.notes)
    return "\n".join(lines) + "\n"


def format_bambu_template_capture_result(result: BambuStudioTemplateCaptureResult) -> str:
    lines = [
        f"success={result.success}",
        f"copied={result.copied}",
        f"overwrite={result.overwrite}",
        f"output_exists={result.output_exists}",
        f"input_3mf={result.input_3mf}",
        f"output_3mf={result.output_3mf}",
        f"template_check_success={result.template_check.success}",
    ]
    if result.error_text:
        lines.append(f"error_text={result.error_text}")
    if result.notes:
        lines.append("notes:")
        lines.extend(f"- {note}" for note in result.notes)
    return "\n".join(lines) + "\n"


def format_bambu_hammerspoon_setup_result(result: BambuHammerspoonSetupResult) -> str:
    lines = [
        f"success={result.success}",
        f"init_path={result.init_path}",
        f"actions_path={result.actions_path}",
        f"init_existed={result.init_existed}",
        f"init_written={result.init_written}",
        f"restart_requested={result.restart_requested}",
        f"restart_succeeded={result.restart_succeeded}",
        f"hammerspoon_cli_available={result.probe.hammerspoon_cli_available}",
        f"hammerspoon_ipc_ready={result.probe.hammerspoon_ipc_ready}",
    ]
    if result.error_text:
        lines.append(f"error_text={result.error_text}")
    if result.notes:
        lines.append("notes:")
        lines.extend(f"- {note}" for note in result.notes)
    return "\n".join(lines) + "\n"
