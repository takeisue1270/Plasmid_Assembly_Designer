# Workbook layout

The oligo workbook and the project workbook are the two records this procedure
keeps in step with the maps. The layout below is the one the defaults in
`config.json` assume. It is the layout of the author's laboratory, and every
value in it — sheet names, column numbers, formulas, numbering — is
configuration, not code. To use a different layout, change `config.json`; see
[`configuration.md`](configuration.md).

| what | config key | default |
|---|---|---|
| plasmid maps | `paths.plasmid_dir` | `plasmids/*.dna` |
| oligo master | `paths.oligo_workbook` + `sheets.oligo` | `oligos.xlsx`, sheet `Oligos` |
| project record | `paths.progress_workbook` + `sheets.project` | `projects.xlsx`, sheet `Projects` |
| block template | `sheets.template` | sheet `Template` |
| registration reports | `paths.report_dir` | `reports/` |
| Excel backups | `paths.backup_dirname` | a `Backup/` folder beside the workbook |
| primer registrar | `paths.registrar` (local only) | a `snapgene-primer-registrar` checkout |

Relative paths resolve against `paths.project_root`, which is set in
`config.local.json` or in `PLASMID_CLONING_ROOT`.

## Excel mechanics

Both workbooks are masters that may carry comments and links, so **write them
through Excel (COM, or by hand), never through openpyxl** — an openpyxl round
trip drops comments and links. Back up to the `Backup/` folder first, and diff
against that backup afterwards.

A workbook may be open while you work. Check before writing:

```powershell
$xl = [System.Runtime.InteropServices.Marshal]::GetActiveObject("Excel.Application")
foreach ($wb in $xl.Workbooks) { "$($wb.Name) Saved=$($wb.Saved)" }
```

If the workbook is open, attach to that running instance and edit it there;
`Workbooks.Open` on an already-open file fails with "cannot access the file".
Confirm `Saved=True` first so you are not discarding unsaved edits. While a
workbook is open, `openpyxl` may also fail to *read* it — verify through COM
instead, or copy the file and read the copy.

PowerShell pitfalls:

- `.Formula = $someInt` throws `Cannot convert Int32 to String`. Use `.Value2`
  for numbers and dates.
- `$xl.CutCopyMode = 0` throws in PowerShell 5.1. Use `$xl.CutCopyMode = $false`.
- A pasted cell inherits the template's number format. After pasting, set the
  format explicitly on every numeric and date column you wrote.
- Dates: write `yyyy/mm/dd` and set the display format to `yyyy/mm/dd` too.

When diffing two workbooks with openpyxl, normalise `ArrayFormula` objects
(`(v.ref, v.text)`) — they have no `__eq__`, so a naive comparison reports every
array formula as changed. Also note `zip()` truncates to the shorter sheet, so
rows added past the old `max_row` silently escape the comparison.

## Oligo sheet

Column numbers come from `oligo_sheet` in `config.json`
(`id_column` 1, `name_column` 2, `sequence_column` 3).

| col | content |
|---|---|
| A | Oligo No. (pre-filled) |
| B | **Name** — write this |
| C | **Sequence** — write this |
| D, E, K, L | `Concat.`, `Length`, `Price`, `Tax+` — formulas, already present |
| F, G, H | Design / Order / Arrival dates |

Only B and C are written by hand. The ID in A and the formulas in D/E/K/L are
already laid out on blank rows; find the first row whose A has an ID and whose B
and C are empty.

**Each series (`O01`, `O02`, …) is exactly `oligo_sheet.series_size` rows (81).**
When fewer than you need are left, start the next series rather than extending
the current one: copy the last row's `oligo_sheet.copy_columns` (`A:S`) down that
many rows to inherit the formats and formulas, then overwrite column A with
`O02-01` … `O02-81`.

Naming: `<target>.<role>` with `.as` for the antisense partner of an annealed
pair, and `F`/`R` for PCR primers.

- gRNA cloning oligos: `GeneA.gRNA.1` / `GeneA.gRNA.1.as`
- HiFi primers are named for the junction they create, in 5'→3' order:
  `GeneA-GeneB.F` (from the GeneA-derived flap into the GeneB ORF),
  `IRES-GeneB.R`, `GeneA.3p-GeneC.R`, `TTS-IRES.F`
  (`TTS` = the translation termination site the backbone primer starts after).

Sense/annealing parts go in upper case, flaps and plain backbone primers in
lower case.

## Project sheet block

The layout has 33 columns, mapped in `project_sheet.columns`. Copy
`project_sheet.template_range` (`A18:AG22`) from the template sheet rather than
copying an older block's column positions. Leave
`blank_rows_between_blocks` (1) between blocks.

| col | header | GGA | HiFi |
|---|---|---|---|
| A | (block label) | header row only | header row only |
| B | Project No. | project number on the first row, `=B{prev}` after |||
| C | Sub. No. | `1`, `2`, … as numbers (the format renders `01`) |||
| D | Method | `GGA` | `HiFi` |
| E | Plasmid map | design date |||
| F | Length | product bp |||
| G | Plasmid name | `<prefix>.<name>`, where the prefix is 8 characters |||
| H | RE1 | `gga.default_enzyme` (`BbsI-HF`) | backbone PCR **forward** primer, or the enzyme if cut |
| I | RE2 | — | backbone PCR **reverse** primer, or the 2nd enzyme |
| J | Backbone plasmid/gDNA | backbone plasmid No. |||
| K | Backbone prep. | (wet lab) |||
| L | Length (bp) | backbone bp | backbone amplicon bp |
| M | PCR primer/Oligo 1 | sense oligo | insert **forward** primer |
| N | PCR primer/Oligo 2 | antisense oligo | insert **reverse** primer |
| O | Template | — | PCR template plasmid |
| P | Length (bp) | — | insert amplicon bp |
| Q–X | PCR/Annealing … Plasmid No. | (wet lab) |||
| Y | Plasmid name | `=MID(G{r},9,150)` |||
| Z | Competent cell | `DH5alpha` |||
| AA | Conc | (wet lab) |||
| AB | Design | `=E{r}` |||
| AC | Order | (wet lab) |||
| AD | Obtained | `=TODAY()` |||
| AE | Made by | `project_sheet.defaults.made_by` (set in `config.local.json`) |||
| AF | Entered by | `project_sheet.defaults.entered_by` (set in `config.local.json`) |||
| AG | Project number | `=B{r}&"_"&C{r}` |||

`Y` is `=MID(G,9,150)`: it strips the 8-character prefix, so the plasmid name in
G must keep that exact prefix width. The template sheet shows `=G{r}` there only
because its own G is blank — use `MID`, as every filled row does.

`AD` is `=TODAY()` in the template, but some blocks hold the sequence-check date
(`=W{r}`) instead. `=TODAY()` is volatile and so means nothing once the bench
work is done; choose one and keep it the same within a project.

When the backbone is PCR-amplified rather than cut, its two primers go in
`RE1`/`RE2`.
