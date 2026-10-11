"""Configuration resolves in the documented order and nothing is hard-coded."""

from __future__ import annotations

import json
from pathlib import Path

import config
import pytest


def test_defaults_are_the_published_names():
    cfg = config.Config()
    assert cfg.sheet("oligo") == "Oligos"
    assert cfg.sheet("project") == "Projects"
    assert cfg.sheet("template") == "Template"


def test_an_override_wins_and_does_not_leak_into_the_default():
    over = config.load({"sheets": {"oligo": "primers"}})
    assert over.sheet("oligo") == "primers"
    assert config.load().sheet("oligo") == "Oligos"


def test_an_explicit_argument_beats_the_configured_name():
    cfg = config.Config()
    assert cfg.sheet("oligo", "whatever") == "whatever"


def test_relative_paths_resolve_against_the_project_root(tmp_path):
    cfg = config.Config({"paths": {"project_root": str(tmp_path)}})
    assert cfg.path("oligo_workbook") == tmp_path / "oligos.xlsx"
    assert cfg.path("plasmid_dir") == tmp_path / "plasmids"


def test_an_absolute_path_is_used_as_given(tmp_path):
    other = tmp_path / "elsewhere" / "Oligos.xlsx"
    cfg = config.Config({"paths": {"project_root": str(tmp_path),
                                   "oligo_workbook": str(other)}})
    assert cfg.path("oligo_workbook") == other


def test_an_explicit_path_argument_beats_configuration(tmp_path):
    cfg = config.Config({"paths": {"project_root": str(tmp_path)}})
    assert cfg.path("oligo_workbook", "D:/lab/x.xlsx") == Path("D:/lab/x.xlsx")


def test_backup_dir_sits_beside_the_workbook(tmp_path):
    cfg = config.Config({"paths": {"project_root": str(tmp_path)}})
    wb = cfg.path("progress_workbook")
    assert cfg.backup_dir(wb) == wb.parent / "Backup"


def test_missing_project_root_raises_a_useful_error(monkeypatch, tmp_path):
    monkeypatch.delenv("PLASMID_CLONING_ROOT", raising=False)
    empty = tmp_path / "empty.json"
    empty.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("PLASMID_CLONING_CONFIG", str(empty))
    with pytest.raises(config.ConfigError, match="PLASMID_CLONING_ROOT"):
        _ = config.Config().project_root


def test_environment_variable_supplies_the_project_root(monkeypatch, tmp_path):
    empty = tmp_path / "empty.json"
    empty.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("PLASMID_CLONING_CONFIG", str(empty))
    monkeypatch.setenv("PLASMID_CLONING_ROOT", str(tmp_path))
    assert config.Config().project_root == tmp_path


def test_a_replacement_config_file_changes_the_names(monkeypatch, tmp_path):
    alt = tmp_path / "alt.json"
    alt.write_text(json.dumps({"sheets": {"oligo": "primers", "project": "Builds"},
                               "paths": {"project_root": str(tmp_path),
                                         "oligo_workbook": "lab/Oligos.xlsx"}}),
                   encoding="utf-8")
    monkeypatch.setenv("PLASMID_CLONING_CONFIG", str(alt))
    cfg = config.Config()
    assert cfg.sheet("oligo") == "primers"
    assert cfg.sheet("project") == "Builds"
    assert cfg.sheet("template") == "Template"      # untouched keys keep the default
    assert cfg.path("oligo_workbook") == tmp_path / "lab/Oligos.xlsx"


def test_published_config_carries_no_machine_paths():
    """config.json is published, so it must not contain anyone's directory tree."""
    raw = json.loads((Path(config.DEFAULTS)).read_text(encoding="utf-8"))
    assert "project_root" not in raw["paths"]
    assert "registrar" not in raw["paths"]


def test_published_config_names_nobody():
    """config.json is published, so it must not name a real person.

    `Made by` and `Entered by` are people's names. They belong in
    config.local.json, which is gitignored; the published defaults stay empty.
    """
    raw = json.loads((Path(config.DEFAULTS)).read_text(encoding="utf-8"))
    assert raw["project_sheet"]["defaults"]["made_by"] == ""
    assert raw["project_sheet"]["defaults"]["entered_by"] == ""


def test_the_constants_the_workflow_depends_on_are_configuration():
    cfg = config.Config()
    assert cfg["hifi"]["flap_length"] == 20
    assert cfg["gga"]["sense_prefix"] == "CACCG"
    assert cfg["gga"]["antisense_prefix"] == "AAAC"
    assert cfg["oligo_sheet"]["series_size"] == 81
    assert set(cfg["dna_blocks"]["keep"]) & set(cfg["dna_blocks"]["drop"]) == set()
