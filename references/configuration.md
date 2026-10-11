# Configuration

No workbook name, sheet name or directory is written into the code. Everything
is resolved through `scripts/config.py`, first hit wins:

1. an explicit argument — a CLI flag, or a `cfg`/override passed to a function
2. an environment variable
3. `config.local.json` (machine-specific, **not published**)
4. `config.json` (the published defaults)

When nothing names a workbook or a sheet, the configured default applies. Pass
an override only when a run needs a different file or sheet.

## What lives where

`config.json` holds **names only**, so it is safe to publish:

| key | default |
|---|---|
| `paths.plasmid_dir` | `plasmids` |
| `paths.oligo_workbook` | `oligos.xlsx` |
| `paths.progress_workbook` | `projects.xlsx` |
| `paths.report_dir` | `reports` |
| `paths.backup_dirname` | `Backup` |
| `sheets.oligo` | `Oligos` |
| `sheets.project` | `Projects` |
| `sheets.template` | `Template` |

plus the oligo sheet's column numbers and series size, the project sheet's column map,
formulas and defaults, the GGA oligo prefixes, the HiFi flap length, and the
`.dna` block ids to keep and drop.

The relative paths are resolved against the project root. An absolute value is
used as given, so a workbook anywhere on disk can be named directly.

`config.local.json` holds the **machine paths and the operator names**, which
are deliberately absent from `config.json`:

| key | what |
|---|---|
| `paths.project_root` | the tree holding the workbooks and the plasmid maps |
| `paths.registrar` | a checkout of `snapgene-primer-registrar` |
| `project_sheet.defaults.made_by` | the `Made by` column (`AE`) |
| `project_sheet.defaults.entered_by` | the `Entered by` column (`AF`) |

The two names are empty strings in `config.json` so that no real person is
named in the published package; set them here and the project-sheet block picks them
up. Keep it out of the repository. If it is missing, both can come from
`PLASMID_CLONING_ROOT` and `PLASMID_CLONING_REGISTRAR`, and the registrar is
also looked for in `~/repos`, `~/Documents` and beside the package.

## Overriding

```powershell
# a different workbook and sheet for one run
python scripts\dna_edit.py --oligo-workbook "D:\lab\Oligos.xlsx" --oligo-sheet "primers" ...

# a whole alternative layout
$env:PLASMID_CLONING_CONFIG = "D:\lab\plasmid-cloning.json"
```

Every script accepts `--config`, `--project-root`, `--registrar`,
`--plasmid-dir`, `--oligo-workbook`, `--oligo-sheet`, `--progress-workbook`,
`--project-sheet` and `--template-sheet` (added by `config.add_arguments`).

From Python:

```python
import config
cfg = config.load()                                  # defaults
cfg = config.load({"sheets": {"oligo": "primers"}})  # one override
cfg.path("oligo_workbook")      # Path, resolved against the project root
cfg.sheet("project")            # "Projects"
cfg["project_sheet"]["columns"]["plasmid_name"]      # 7
```

## Type IIS enzymes other than BbsI

Nothing in the scripts is tied to BbsI. `dna_edit.py` replaces whatever sits
between `--start` and `--end` and drops whatever `--drop-feature` names, and
`verify_product.py` compares names and bases. Neither reads an enzyme, so a
vector cut with BsaI, BsmBI/Esp3I or SapI goes through the same two calls.

What does change with the enzyme is in `config.json`, under `gga`:

| key | default | change it when |
|---|---|---|
| `sense_prefix` | `CACCG` | the vector's overhangs differ |
| `antisense_prefix` | `AAAC` | the vector's overhangs differ |
| `antisense_suffix` | `C` | the vector's overhangs differ |
| `spacer_length` | `20` | the protospacer is not 20 nt |
| `insert_feature_name` | `target_seq.` | the insert should be labelled otherwise |
| `stuffer_feature_match` | `BbsI` | the stuffer feature is named after another enzyme |
| `default_enzyme` | `BbsI-HF` | the `RE1` column should record another enzyme |

These are read while designing, by whoever is following `docs/method.md`.
Of the `gga` section only `insert_feature_color` is read by a script
(`dna_edit.py`, as the default for `--feature-color`). The splice coordinates
are not configuration at all: they depend on where a given vector's stuffer
sits, and `--list-features` is how you find it.

## Porting to another lab

Copy `config.json`, change the names and the column map, and point
`PLASMID_CLONING_CONFIG` at it. The parts that are the author's laboratory's own
conventions — the project sheet's column order, the oligo series of 81,
`DH5alpha` — are all values in that file, not assumptions in the code. The `Made by` and
`Entered by` names belong in `config.local.json` instead, so that they stay out
of any repository.

Two things are not configuration and will not port by editing JSON: the GGA
splice coordinates depend on where a given vector's stuffer sits, and the
`.dna` block handling depends on SnapGene's format. Both are documented in
[`docs/method.md`](../docs/method.md).
