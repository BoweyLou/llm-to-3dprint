from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any


TEXT_TO_CAD_SKILL_ENV = "TEXT_TO_CAD_SKILL_DIR"


@dataclass(slots=True)
class CadSkillsProbe:
    skill_dir: str | None
    available: bool
    step_script: str | None = None
    inspect_script: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CadSkillsCommandResult:
    command: list[str]
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    skipped: bool = False

    @property
    def success(self) -> bool:
        return not self.skipped and self.returncode == 0


@dataclass(slots=True)
class CadSkillsPilotReport:
    probe: CadSkillsProbe
    generator: str
    output_dir: str
    ran: bool
    step: CadSkillsCommandResult
    inspect: CadSkillsCommandResult
    cad_explorer_links: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def passes(self) -> bool:
        if not self.ran:
            return self.probe.available
        return self.step.success and self.inspect.success

    def to_dict(self) -> dict[str, Any]:
        return {
            "probe": self.probe.to_dict(),
            "generator": self.generator,
            "output_dir": self.output_dir,
            "ran": self.ran,
            "passes": self.passes,
            "step": asdict(self.step),
            "inspect": asdict(self.inspect),
            "cad_explorer_links": self.cad_explorer_links,
            "notes": self.notes,
        }


def probe_cad_skills(skill_dir: str | Path | None = None) -> CadSkillsProbe:
    configured_value = skill_dir if skill_dir is not None else os.environ.get(TEXT_TO_CAD_SKILL_ENV)
    if configured_value is None or str(configured_value).strip() == "":
        return CadSkillsProbe(
            skill_dir=None,
            available=False,
            notes=[f"Set {TEXT_TO_CAD_SKILL_ENV} to a text-to-cad/CAD Skills checkout."],
        )
    configured = Path(configured_value).expanduser()
    step_script = configured / "scripts" / "step"
    inspect_script = configured / "scripts" / "inspect"
    notes = []
    if not configured.exists():
        notes.append("Configured CAD Skills directory does not exist.")
    if not step_script.exists():
        notes.append("Missing scripts/step.")
    if not inspect_script.exists():
        notes.append("Missing scripts/inspect.")
    available = configured.exists() and step_script.exists() and inspect_script.exists()
    return CadSkillsProbe(
        skill_dir=str(configured),
        available=available,
        step_script=str(step_script) if step_script.exists() else None,
        inspect_script=str(inspect_script) if inspect_script.exists() else None,
        notes=notes,
    )


def run_cad_skills_pilot(
    generator: str | Path,
    output_dir: str | Path,
    *,
    skill_dir: str | Path | None = None,
    run: bool = False,
) -> CadSkillsPilotReport:
    probe = probe_cad_skills(skill_dir)
    generator_path = Path(generator)
    output = Path(output_dir)
    step_command = (
        [probe.step_script, str(generator_path), "--output-dir", str(output)]
        if probe.step_script
        else []
    )
    inspect_command = (
        [probe.inspect_script, str(output)]
        if probe.inspect_script
        else []
    )
    notes = [
        "This adapter intentionally shells out to an external CAD Skills checkout instead of vendoring it.",
        "Use it only for explicit clean-CAD pilot targets; mesh-preserved and Bambu handoff workflows remain repo-owned.",
    ]
    if not probe.available:
        notes.extend(probe.notes)
        return CadSkillsPilotReport(
            probe=probe,
            generator=str(generator_path),
            output_dir=str(output),
            ran=False,
            step=CadSkillsCommandResult(command=step_command, skipped=True),
            inspect=CadSkillsCommandResult(command=inspect_command, skipped=True),
            notes=notes,
        )
    if not run:
        notes.append("Dry run only; pass --run to execute scripts/step and scripts/inspect.")
        return CadSkillsPilotReport(
            probe=probe,
            generator=str(generator_path),
            output_dir=str(output),
            ran=False,
            step=CadSkillsCommandResult(command=step_command, skipped=True),
            inspect=CadSkillsCommandResult(command=inspect_command, skipped=True),
            notes=notes,
        )

    output.mkdir(parents=True, exist_ok=True)
    step_result = _run_command(step_command)
    inspect_result = _run_command(inspect_command)
    links = _extract_links("\n".join([step_result.stdout, step_result.stderr, inspect_result.stdout, inspect_result.stderr]))
    return CadSkillsPilotReport(
        probe=probe,
        generator=str(generator_path),
        output_dir=str(output),
        ran=True,
        step=step_result,
        inspect=inspect_result,
        cad_explorer_links=links,
        notes=notes,
    )


def write_cad_skills_pilot_report(report: CadSkillsPilotReport, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report.to_dict(), indent=2) + "\n")
    return destination


def format_cad_skills_probe(probe: CadSkillsProbe) -> str:
    status = "available" if probe.available else "unavailable"
    lines = [f"CAD Skills {status}: {probe.skill_dir or 'not configured'}"]
    if probe.step_script:
        lines.append(f"- step: {probe.step_script}")
    if probe.inspect_script:
        lines.append(f"- inspect: {probe.inspect_script}")
    for note in probe.notes:
        lines.append(f"- note: {note}")
    return "\n".join(lines)


def format_cad_skills_pilot_report(report: CadSkillsPilotReport) -> str:
    status = "PASS" if report.passes else "FAIL"
    lines = [
        f"{status} CAD Skills pilot: generator={report.generator}, output_dir={report.output_dir}, ran={report.ran}",
        f"- step: {' '.join(report.step.command) if report.step.command else 'unavailable'}",
        f"- inspect: {' '.join(report.inspect.command) if report.inspect.command else 'unavailable'}",
    ]
    if report.ran:
        lines.append(f"- step returncode: {report.step.returncode}")
        lines.append(f"- inspect returncode: {report.inspect.returncode}")
    for link in report.cad_explorer_links:
        lines.append(f"- CAD Explorer: {link}")
    for note in report.notes:
        lines.append(f"- note: {note}")
    return "\n".join(lines)


def _run_command(command: list[str]) -> CadSkillsCommandResult:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    return CadSkillsCommandResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _extract_links(text: str) -> list[str]:
    return sorted(set(re.findall(r"https?://[^\s)]+", text)))
