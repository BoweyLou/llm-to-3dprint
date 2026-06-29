from __future__ import annotations

from pathlib import Path

from llm_to_3dprint.cad_skills import (
    probe_cad_skills,
    run_cad_skills_pilot,
    write_cad_skills_pilot_report,
)


def test_probe_cad_skills_reports_missing_env(monkeypatch) -> None:
    monkeypatch.delenv("TEXT_TO_CAD_SKILL_DIR", raising=False)

    probe = probe_cad_skills()

    assert probe.available is False
    assert probe.skill_dir is None


def test_cad_skills_pilot_dry_run_with_fake_checkout(tmp_path: Path) -> None:
    skill_dir = tmp_path / "text-to-cad"
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "scripts" / "step").write_text("#!/bin/sh\nexit 0\n")
    (skill_dir / "scripts" / "inspect").write_text("#!/bin/sh\nexit 0\n")
    generator = tmp_path / "part.py"
    generator.write_text("print('build')\n")

    report = run_cad_skills_pilot(generator, tmp_path / "out", skill_dir=skill_dir, run=False)

    assert report.probe.available is True
    assert report.ran is False
    assert report.step.skipped is True
    assert str(skill_dir / "scripts" / "step") in report.step.command


def test_write_cad_skills_pilot_report(tmp_path: Path) -> None:
    report = run_cad_skills_pilot("part.py", tmp_path / "out", skill_dir=tmp_path / "missing")
    path = write_cad_skills_pilot_report(report, tmp_path / "report.json")

    assert path.exists()
    assert "Configured CAD Skills directory does not exist" in path.read_text()
