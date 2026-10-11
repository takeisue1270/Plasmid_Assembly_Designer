# Method: designing a GGA or HiFi construct

This is the procedure the scripts implement. It is written to be followed by
hand: open the maps, do the arithmetic yourself, and use `scripts/` for the
mechanical parts.

One construct normally means all five steps. Do them in order and check each
one before moving on.

1. Design the oligos from the actual sequences, never from the plasmid names.
2. Register the new oligos in the oligo workbook's oligo sheet.
3. Build the product `.dna` from the backbone `.dna`.
4. Register the oligos as SnapGene primers.
5. Add a `Plasmid Construction` block to the project sheet.

[`references/workbook-layout.md`](../references/workbook-layout.md) holds the
column maps, numbering rules and Excel mechanics. Read it before touching either
workbook.

## Configuration

No file name, sheet name or directory is written into the code. They all come
from `config.json` through `scripts/config.py`, and every script takes
`--oligo-workbook`, `--oligo-sheet`, `--progress-workbook`, `--project-sheet`,
`--plasmid-dir` and friends.

When nothing names a workbook or a sheet, the configured default applies —
`oligos.xlsx` / `Oligos`, `projects.xlsx` / `Projects` / `Template`, and
`plasmids/` for the maps. Pass an override only for a different file or sheet,
and write down which workbook and sheet you wrote to.

[`references/configuration.md`](../references/configuration.md) has the full
key list and how to point the package at another lab's layout.

## Work out the design from the files

Always open the backbone and the template `.dna` and read the bases. Plasmid
*names* are descriptive, not authoritative. Two real cases: one map's filename
named a different fragment from the one its own feature label named, and
another map's name said nothing about a FLAG tag whose stop codon the reverse
primer then had to supply.

Find the precedent before designing anything new. Nearly every construct is the
n-th member of a series, and the earlier member tells you which columns, which
enzyme, which primer naming and which boundary are actually in use. The project
sheet is the index: find the project that built the backbone, or an earlier
project with the same shape.

When a precedent exists, reproduce it mechanically and check your arithmetic
against it. The GGA splice below was confirmed by applying it to an existing
vector with an already-cloned protospacer and getting that known product's
sequence back byte-for-byte. Do that kind of check — it catches an off-by-one
before it reaches an oligo order.

## Method: GGA (annealed oligo pair into a 2× Type IIS vector)

Used to drop a 20-nt gRNA protospacer into a vector whose cloning site is a
2× Type IIS stuffer sitting right after a `caccg`.

The enzyme never reaches the scripts: the splice is driven by the stuffer's
coordinates and its feature name, so a vector cut with BbsI, BsaI, BsmBI/Esp3I
or SapI follows the same recipe. What does change with the enzyme is the
overhang, so check `gga.sense_prefix` / `antisense_prefix` / `antisense_suffix`
and `gga.stuffer_feature_match` in `config.json` before reusing the `CACCG` /
`AAAC` pair on a vector that is not a BbsI one.

- **sense** = `CACCG` + N20, **antisense** = `AAAC` + revcomp(N20) + `C`.
  Both are exactly 25 nt. Always the full 20 nt, even when the protospacer
  already starts with G — the vector's own `g` (last base of `…gaaacaccg`)
  supplies the G of `CACCG`, so the spacer becomes 21 nt. That is intended, and
  it is consistent across the whole series.
- In the author's vectors the stuffer is 1-based **282..298**
  (`ggtcttcgagaagacct`). Confirm it in your own map with `--list-features`, as
  the coordinates are vector-specific. The product is

  ```
  product = backbone[:281] + N20 + backbone[298:]        # 0-based slices, +3 bp
  ```

  so `backbone[:281]` ends with `…ggacgaaacaccg` and `backbone[298:]` starts
  with `gtttaagagc`.
- Annotate the insert as a `misc_feature` named `target_seq.` at **282..301**,
  colour `#ffff99`, and delete the stuffer feature, reusing its `recentID`.
  Shift every feature coordinate ≥ 299 by +3.
- The sense oligo then matches the product exactly at 277..301 and the
  antisense at 281..305 on the minus strand. Check that — it is the cheapest
  proof the splice landed correctly.

## Method: HiFi assembly

**The rule: every fragment is produced by PCR, and each junction is made by a
20-nt flap on a primer. This applies even when the backbone is prepared by
restriction digestion** — the backbone is not amplified in that case, but the
insert primers still carry the 20-nt flap matching the cut ends.

- **Backbone primers** are plain 20-mers sitting at the two junction points,
  pointing away from the region being replaced.
- **Insert primers** = 20-nt flap + ~20 nt annealing to the template. The flap
  is the neighbouring fragment's terminal 20 nt, in the orientation that makes
  the assembled product seamless:
  - insert-F flap = the 20 nt immediately 5' of the insertion point on the backbone
  - insert-R flap = revcomp of the backbone-F primer (its full 20 nt)
- Write the flap in lower case and the annealing part in upper case, as the
  existing oligos do: `nnnnnnnnnnnnnnnnnnnnNNNNNNNNNNNNNNNNNNNN`, that is
  20 lower-case bases taken from the neighbouring fragment, then the part that
  anneals to the template.
- **Do not shorten the flap to match an apparent overlap.** A shared base at
  the junction can make the real overlap longer than 20. In one series the
  ORF's `TAA` stop codon happened to be the first three bases of the backbone
  too, so the overlap read 20 nt while the flap written into the primer was 17.
  Copying that 17 into a backbone that does *not* start with `taa` silently
  deletes three bases. Always derive the flap as the full 20 nt of the
  neighbour and let the overlap come out however long it comes out.
- Check the arithmetic: `len(product) = Σ amplicons − Σ overlaps`.
- Reuse existing oligos wherever the sequence matches exactly. Compute the
  primer you would design, then search the `Oligo` sheet for that exact string
  before creating a new ID. In one run both insert-F primers already existed in
  the sheet, so only 4 new oligos were needed instead of 9.
- One primer usually serves several constructs. Group the targets by their
  terminal sequence and design one primer per distinct end, not one per
  construct.

## Building the product .dna

Use `scripts/dna_edit.py`. It reads the backbone `.dna`, splices the sequence,
rewrites the features block and writes a new `.dna` that SnapGene opens.

```bash
python scripts/dna_edit.py --help
```

What it does, and why:

- **Keeps** blocks 9, 0, 3, 8, 10, 5, 6, 13, 28, 14 and **drops** 2, 7, 11, 16,
  17, 27. The dropped ones are the parent's cached data (2), its edit history
  (7, 11, 27) and its sequencing alignments (16, 17). All of those are keyed to
  the parent's coordinates, so carrying them into a derivative with a different
  length would show reads aligned to the wrong places. Block 2 is genuinely
  optional — a map written by SnapGene itself has none.
- The features block is **not valid UTF-8** (it can carry Shift-JIS bytes in
  Japanese notes). Decode and encode it as `latin1` so the round trip is
  byte-exact. Features use **1-based inclusive** `range="A-B"`; the primers
  block uses **0-based inclusive** `location=` / `hybridizedRange=`.
- Features that overlap the replaced region cannot carry over — drop them by
  name, and write down which ones you dropped.
- For a large replacement, **empty the primers block** (`--strip-primers`) and
  let the registrar rebuild it from the spreadsheet. That is more reliable than
  shifting forty coordinates, and it drops primers that no longer bind.
- Give the product a fresh UUID in the Notes block and update the description.

Then run `scripts/verify_product.py`, which asserts the things that must hold:
product length, both flanks identical to the backbone, the inserted segment
equal to what you designed, each designed primer occurring exactly once, the
new feature covering exactly the insert, and every surviving parent feature
still sitting on the same bases. It exits non-zero and names the file.

**Never take the builder's own output as proof.** Two real errors were caught
only by the verifier: a `Length (bp)` cell that inherited a date format and
rendered 10859 as `1929/9/23`, and the 17-vs-20 flap error above.

## Registering the oligos and primers

Write the new oligos into the oligo sheet (names in **B**, sequences in **C**)
following [`references/workbook-layout.md`](../references/workbook-layout.md),
then run
[snapgene-primer-registrar](https://github.com/takeisue1270/Registering_Primers_in_SnapGene):
a dry run first, read the report, then `--apply`, then an independent check that
each stored primer sequence and binding site matches the spreadsheet.

Watch for an oligo that duplicates an existing one under a different name. The
registrar merges rows only when **name and sequence both** match, so a
re-designed primer with a new name registers as a second primer on the same
site and gets ordered twice. Before adding a new row, search column C for the
sequence — and read the cached value, because some rows hold `=CONCAT(...)`
formulas rather than literal text, and `openpyxl` without `data_only=True`
returns the formula and silently misses the duplicate.

## The project-record entry

Copy the template range from the template sheet into the next free rows of the
project sheet, leaving one blank row after the previous block, then overwrite
the values. The column map and the per-cell formulas are in
[`references/workbook-layout.md`](../references/workbook-layout.md).

Leave the wet-lab columns (`Backbone prep.`, `PCR/Annealing`, `DpnI`,
`Transformation`, `Miniprep`, `Plasmid Ext.`, `Nanopore`, `Sequence check`,
`Plasmid No.`) empty — this procedure records the design, not the bench work.

## What to write down

Keep, with the construct: the oligo table (name, ID, sequence, length), the
product names with their lengths, the backbone and the template, the amplicon
sizes for HiFi, and what you verified. Then note every judgement call — the
junction boundary, which column the backbone went in, any primer you reused —
because those are the parts someone will later want to check or correct.
