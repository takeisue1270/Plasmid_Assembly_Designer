"""Resolve the names and paths this workflow uses.

Nothing in the package hard-codes a workbook name, a sheet name or a machine
path. Every one of them is looked up here, so the same code runs against
another lab's file layout by changing configuration rather than source.

Resolution order, first hit wins:

    1. an explicit argument passed by the caller (CLI flag or function kwarg)
    2. an environment variable
    3. config.local.json next to config.json   (machine-specific, not published)
    4. config.json                             (the published defaults)

`config.json` holds only *names* — workbook filenames, sheet names, column
numbers, formulas. Those are the lab's conventions and are safe to publish.
Absolute paths are deliberately absent from it: `project_root` (the tree that
holds the workbooks and the plasmid maps) and `registrar` (a clone of
snapgene-primer-registrar) must come from the environment or config.local.json,
so the published package carries nobody's directory layout.

Environment variables
---------------------
PLASMID_CLONING_CONFIG     path to a JSON file replacing config.local.json
PLASMID_CLONING_ROOT       project root
PLASMID_CLONING_REGISTRAR  snapgene-primer-registrar checkout
"""

from __future__ import annotations

import json
import os
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
DEFAULTS = PKG / "config.json"
LOCAL = PKG / "config.local.json"


def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


class ConfigError(RuntimeError):
    pass


class Config:
    def __init__(self, overrides=None):
        data = json.loads(DEFAULTS.read_text(encoding="utf-8"))
        local_path = Path(os.environ.get("PLASMID_CLONING_CONFIG") or LOCAL)
        self.local_path = local_path if local_path.is_file() else None
        if self.local_path:
            data = _merge(data, json.loads(self.local_path.read_text(encoding="utf-8")))
        self._d = _merge(data, overrides or {})

    # -- names -----------------------------------------------------------
    def sheet(self, which, override=None):
        """Sheet name. `which` is one of oligo / project / template."""
        if override:
            return override
        try:
            return self._d["sheets"][which]
        except KeyError:
            raise ConfigError(f"no sheet named {which!r} in configuration") from None

    def section(self, name):
        return self._d[name]

    def __getitem__(self, name):
        return self._d[name]

    # -- paths -----------------------------------------------------------
    @property
    def project_root(self):
        v = (self._d.get("paths", {}).get("project_root")
             or os.environ.get("PLASMID_CLONING_ROOT"))
        if not v:
            raise ConfigError(
                "project root is not configured. Set PLASMID_CLONING_ROOT, or put\n"
                '  {"paths": {"project_root": "..."}}\n'
                f"in {LOCAL}")
        return Path(v)

    @property
    def registrar(self):
        v = (self._d.get("paths", {}).get("registrar")
             or os.environ.get("PLASMID_CLONING_REGISTRAR"))
        if v:
            return Path(v)
        for guess in (Path.home() / "repos" / "snapgene-primer-registrar",
                      Path.home() / "Documents" / "snapgene-primer-registrar",
                      PKG.parent / "snapgene-primer-registrar"):
            if (guess / "snapgene_primers" / "dna_format.py").is_file():
                return guess
        raise ConfigError(
            "snapgene-primer-registrar not found. Set PLASMID_CLONING_REGISTRAR, or put\n"
            '  {"paths": {"registrar": "..."}}\n'
            f"in {LOCAL}")

    def path(self, which, override=None):
        """A configured path, resolved against the project root when relative.

        `which` is one of plasmid_dir / oligo_workbook / progress_workbook /
        report_dir.
        """
        if override:
            return Path(override)
        try:
            v = self._d["paths"][which]
        except KeyError:
            raise ConfigError(f"no path named {which!r} in configuration") from None
        p = Path(v)
        return p if p.is_absolute() else self.project_root / p

    def backup_dir(self, for_file):
        """The backup folder beside a workbook (created on demand by callers)."""
        return Path(for_file).parent / self._d["paths"]["backup_dirname"]


_cached = None


def load(overrides=None):
    """Return the configuration. Cached unless overrides are supplied."""
    global _cached
    if overrides:
        return Config(overrides)
    if _cached is None:
        _cached = Config()
    return _cached


def add_arguments(ap):
    """Add the standard override flags to an ArgumentParser."""
    g = ap.add_argument_group("configuration (defaults come from config.json)")
    g.add_argument("--config", help="JSON file overriding config.json")
    g.add_argument("--project-root", help="tree holding the workbooks and plasmid maps")
    g.add_argument("--registrar", help="snapgene-primer-registrar checkout")
    g.add_argument("--plasmid-dir", help="directory of .dna plasmid maps")
    g.add_argument("--oligo-workbook", help="oligo master workbook (.xlsx)")
    g.add_argument("--oligo-sheet", help="sheet name inside the oligo workbook")
    g.add_argument("--progress-workbook", help="project record workbook (.xlsx)")
    g.add_argument("--project-sheet", help="sheet name holding the project blocks")
    g.add_argument("--template-sheet", help="sheet name holding the block template")
    return ap


def from_arguments(args):
    """Build a Config from parsed arguments produced by add_arguments()."""
    if getattr(args, "config", None):
        os.environ["PLASMID_CLONING_CONFIG"] = args.config
    paths, sheets = {}, {}
    for flag, key in (("project_root", "project_root"), ("registrar", "registrar"),
                      ("plasmid_dir", "plasmid_dir"), ("oligo_workbook", "oligo_workbook"),
                      ("progress_workbook", "progress_workbook")):
        v = getattr(args, flag, None)
        if v:
            paths[key] = v
    for flag, key in (("oligo_sheet", "oligo"), ("project_sheet", "project"),
                      ("template_sheet", "template")):
        v = getattr(args, flag, None)
        if v:
            sheets[key] = v
    over = {}
    if paths:
        over["paths"] = paths
    if sheets:
        over["sheets"] = sheets
    return load(over or None)
