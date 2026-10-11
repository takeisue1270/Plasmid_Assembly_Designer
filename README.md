# Plasmid Assembly Designer

A documented procedure and two command-line tools for designing Golden Gate
(GGA) and HiFi assembly constructs from SnapGene `.dna` maps, and for keeping
the oligo list, the product maps and the project record consistent.

## Purpose

A cloning design is commonly taken from the plasmid name and from the previous
construct's spreadsheet row. Neither is authoritative. A file name can disagree
with the feature inside the file, and a flap copied from an earlier row can be
wrong for a different backbone. This package derives the design from the bases
in the `.dna` maps, builds the product map by splicing the backbone file
itself, and re-reads the product from disk to confirm it before any oligo is
ordered.

## Scope

One construct is five steps. The table states what this repository provides for
each of them.

| step | provided here |
| --- | --- |
| 1. Design the oligos from the sequences | design rules — [`docs/method.md`](docs/method.md) |
| 2. Add the new oligos to the oligo workbook | layout and numbering — [`references/workbook-layout.md`](references/workbook-layout.md); entered by hand |
| 3. Build the product `.dna` from the backbone | `scripts/dna_edit.py` |
| 4. Register the oligos as SnapGene primers | companion tool [snapgene-primer-registrar](https://github.com/takeisue1270/Registering_Primers_in_SnapGene) |
| 5. Append a construction block to the project sheet | column map and formulas — [`references/workbook-layout.md`](references/workbook-layout.md); entered by hand |

Step 3 is checked with `scripts/verify_product.py`. The check is part of the
procedure, not an option.

The tools take the sequence you give them. They do not choose a gRNA target,
predict off-target sites or check specificity.

## Methods

**GGA.** An annealed oligo pair is cloned into a vector carrying a 2× Type IIS
stuffer; a 20 nt gRNA protospacer is the usual case. The sense oligo is `CACCG`
+ N20 and the antisense `AAAC` + revcomp(N20) + `C`, both 25 nt. The G of
`CACCG` is supplied by the vector's own `g`. These overhangs are BbsI values
held in `config.json`. The scripts are driven by the stuffer's coordinates and
feature name rather than by the enzyme, so a BsaI or BsmBI vector takes the
same call with the overhangs changed.

**HiFi assembly.** Every fragment is produced by PCR, and every junction is
made by a 20 nt flap on a primer. This holds when the backbone is prepared by
restriction digestion as well: the backbone is then not amplified, but the
insert primers still carry the 20 nt flap matching the cut ends. The flap is
always the neighbouring fragment's full terminal 20 nt, and is never shortened
to match an apparent overlap.

## Configuration

No workbook name, sheet name or directory appears in the code. All of them are
values in `config.json`, and anything a caller does not specify falls back to
it.

| key | default |
| --- | --- |
| `paths.plasmid_dir` | `plasmids` |
| `paths.oligo_workbook` | `oligos.xlsx` |
| `paths.progress_workbook` | `projects.xlsx` |
| `sheets.oligo` | `Oligos` |
| `sheets.project` | `Projects` |
| `sheets.template` | `Template` |

`config.json` also holds the column map, the per-cell formulas, the oligo
numbering rule, the GGA prefixes, the HiFi flap length and the `.dna` block
ids. The column map, the formulas and the numbering follow the layout of the
author's laboratory; [`references/workbook-layout.md`](references/workbook-layout.md)
describes it. To run against another layout, copy `config.json`, change the
values, and point `PLASMID_CLONING_CONFIG` at the copy. [`references/configuration.md`](references/configuration.md) lists
every key and the order in which settings resolve.

Absolute paths and personal names are deliberately absent from `config.json`,
so the published package carries no one's directory tree and names no one. The
project root, the location of the primer registrar, and the `Made by` /
`Entered by` names come from `config.local.json`, which is not published. The
two paths can also be given as `PLASMID_CLONING_ROOT` and
`PLASMID_CLONING_REGISTRAR`.

## Requirements

- Python 3.10 or later, with the packages in `requirements.txt`.
- A checkout of snapgene-primer-registrar. `dna_edit.py` reads its `dna_format`
  module, and a checkout placed beside this one is found without configuration.
- Steps 2 and 5 are done in Excel on Windows. The Python tools need neither
  Excel nor a network, and run on Windows, macOS and Linux. CI runs the test
  suite on Ubuntu and Windows with Python 3.10 and 3.12.

## Install

```bash
git clone https://github.com/takeisue1270/Plasmid_Assembly_Designer.git
cd Plasmid_Assembly_Designer
pip install -r requirements.txt

git clone https://github.com/takeisue1270/Registering_Primers_in_SnapGene.git \
    ../snapgene-primer-registrar

cp config.local.json.example config.local.json   # then edit the paths and names
```

## Use

```bash
# what can be dropped from this backbone?
python scripts/dna_edit.py --backbone backbone.dna --list-features

# GGA: swap the 2x Type IIS stuffer at 282..298 for a protospacer
python scripts/dna_edit.py \
    --backbone backbone.dna --out product.dna \
    --start 282 --end 298 --new NNNNNNNNNNNNNNNNNNNN \
    --drop-feature "<stuffer feature>" --feature-name "target_seq."

# HiFi: replace a CDS, and let the registrar rebuild the primer block afterwards
python scripts/dna_edit.py \
    --backbone backbone.dna --out product.dna \
    --start 1232 --end 1834 --new @insert_orf.txt --strip-primers \
    --drop-feature "<old CDS>" --feature-name "<new CDS>" --feature-type CDS

# then check the product
python scripts/verify_product.py \
    --backbone backbone.dna --product product.dna \
    --start 1232 --end 1834 --insert @insert_orf.txt \
    --feature "<new CDS>" --dropped "<old CDS>" --oligo NNNNNNNNNNNNNNNNNNNN
```

Both scripts also accept `--config`, `--project-root`, `--registrar`,
`--plasmid-dir`, `--oligo-workbook`, `--oligo-sheet`, `--progress-workbook`,
`--project-sheet` and `--template-sheet`, and describe their own options with
`--help`.

## Verification

`verify_product.py` re-reads the product from disk and asserts what must hold:
the length arithmetic; both flanks byte-identical to the backbone; the inserted
segment equal to the design; each designed oligo present exactly once; the new
feature covering exactly the insert; and every surviving backbone feature still
sitting on the same bases. It exits non-zero and names the file.

The check catches errors that the builder's own output hides. Two examples: a
flap shortened to 17 nt because a stop codon happened to coincide with the
backbone's first three bases, which on a backbone without that coincidence
deletes three bases; and a `Length (bp)` cell that inherited a date format and
rendered 10859 as `1929/9/23`.

## Contents

| path | content |
| --- | --- |
| `docs/method.md` | the procedure: the five steps, the design rules, the verification discipline |
| `references/configuration.md` | how configuration resolves, every key, how to port it |
| `references/workbook-layout.md` | workbook layouts, numbering, backups, Excel pitfalls |
| `config.json` | default names, column map, formulas and constants |
| `scripts/config.py` | configuration resolution |
| `scripts/dna_edit.py` | splices a `.dna`: sequence, features, primers, notes |
| `scripts/verify_product.py` | re-reads the product and asserts |
| `tests/` | offline tests; no workbook, no Excel, no network |

## Working without the scripts

[`docs/method.md`](docs/method.md) is written to be followed by hand: open the
maps, do the arithmetic, and use `scripts/` for the mechanical parts only.

## What leaves your machine

Nothing. The scripts read and write local files only and open no network
connection.

## Scope and responsibilities

This tool designs nucleic-acid sequences. It does not evaluate whether the
experiment they are for is permitted where you work. Work with engineered
organisms is regulated — in Japan by the Cartagena Act — and your institution's
biosafety committee, not this repository, decides what you may do. Designs for
human germline editing, for gene drives intended for release, and for
increasing the transmissibility or virulence of a pathogen are outside the
intended use of this tool.

The tool places the sequence you supply into the vector as given. It neither
selects a target nor checks specificity. Verify every design experimentally
before you rely on it.

## Disclaimer

This is a research tool, provided as is and without warranty of any kind, as the
[licence](LICENSE) states. It is not intended for diagnostic, therapeutic or
clinical use, and what it returns is a design proposal — check it before you
spend anything on it.

SnapGene, Microsoft Excel and the cloning kits and enzymes named here belong to
the companies that make them. This project is independent of all of them: not
affiliated with, endorsed by, or supported by any of them, and it names them
only to say which file formats it reads and which products the procedure
refers to.

## Citation

Citation metadata is in [`CITATION.cff`](CITATION.cff), which GitHub renders
under "Cite this repository".

## Licence

MIT. See [LICENSE](LICENSE).
