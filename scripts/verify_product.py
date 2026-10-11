"""Re-read a spliced .dna from disk and assert the things that must hold.

Checks, per product:

  * product length == backbone length + delta
  * the two flanks are byte-identical to the backbone
  * the inserted segment equals what was designed
  * every oligo passed with --oligo occurs exactly once (either strand)
  * the annotated insert feature covers exactly the insert and extracts to it
  * every surviving backbone feature still sits on the same bases

Exits non-zero and names the file if anything fails. Driven either from the
command line for a single product, or from another script via `check()`.

    python verify_product.py --backbone backbone.dna --product product.dna \
        --start 1232 --end 1834 --insert @orf.txt \
        --feature GeneB --oligo ACGTACGTACGTACGTACGT --oligo acgtacgtacgt... \
        --dropped GeneA --dropped pA.GeneA
"""

from __future__ import annotations

import argparse
import sys

from Bio import SeqIO
from Bio.Seq import Seq


def _key(name):
    """Normalise a feature name for comparison.

    A name such as "2×BbsI" comes back differently depending on who read it:
    the features XML is decoded as latin1 (so the × arrives as mojibake), while
    BioPython decodes the same label its own way. Comparing on the ASCII-only
    skeleton makes `dropped` work whichever reader supplied the name.
    """
    return "".join(c for c in name if c.isascii())


def _feats(rec):
    out = {}
    for ft in rec.features:
        if ft.type == "primer_bind":
            continue
        lab = (ft.qualifiers.get("label") or [""])[0]
        out.setdefault((ft.type, lab), []).append(
            (int(ft.location.start), int(ft.location.end), ft.location.strand))
    return out


def check(backbone_path, product_path, start, end, insert, *, feature=None,
          oligos=(), dropped=()):
    """Return a list of error strings (empty == pass). Coordinates are 1-based."""
    bb = SeqIO.read(backbone_path, "snapgene")
    pr = SeqIO.read(product_path, "snapgene")
    B, P = str(bb.seq), str(pr.seq)
    U = P.upper()
    ins = insert.upper()
    delta = len(insert) - (end - start + 1)
    errs = []

    if len(P) != len(B) + delta:
        errs.append(f"length {len(P)}, expected {len(B) + delta}")
    if P[:start - 1] != B[:start - 1]:
        errs.append("upstream flank differs from the backbone")
    if P[start - 1 + len(insert):] != B[end:]:
        errs.append("downstream flank differs from the backbone")
    if U[start - 1:start - 1 + len(insert)] != ins:
        errs.append("inserted segment is not the designed sequence")

    for o in oligos:
        o = o.upper()
        n = U.count(o) + U.count(str(Seq(o).reverse_complement()))
        if n != 1:
            errs.append(f"oligo {o[:16]}… occurs {n} times (expected 1)")

    if feature:
        hit = [f for f in pr.features
               if (f.qualifiers.get("label") or [""])[0] == feature]
        if len(hit) != 1:
            errs.append(f"feature {feature!r} appears {len(hit)} times")
        else:
            loc = (int(hit[0].location.start), int(hit[0].location.end))
            if loc != (start - 1, start - 1 + len(insert)):
                errs.append(f"feature {feature!r} at {hit[0].location}, "
                            f"expected {start}..{start - 1 + len(insert)}")
            elif str(hit[0].extract(pr.seq)).upper() != ins:
                errs.append(f"feature {feature!r} does not extract to the insert")

    new = _feats(pr)
    skip = {_key(d) for d in dropped}
    for ft in bb.features:
        if ft.type == "primer_bind":
            continue
        lab = (ft.qualifiers.get("label") or [""])[0]
        if _key(lab) in skip:
            continue
        a, b, st = int(ft.location.start), int(ft.location.end), ft.location.strand
        want = B[a:b]
        exp = (a if a <= start - 1 else a + delta,
               b if b <= end else b + delta, st)
        if ft.type == "source" and a == 0 and b == len(B):
            exp = (0, len(P), st)
        got = new.get((ft.type, lab), [])
        if exp not in got:
            errs.append(f"feature {ft.type}/{lab} expected {exp}, got {got}")
        elif not (ft.type == "source" and a == 0) and P[exp[0]:exp[1]] != want:
            errs.append(f"feature {ft.type}/{lab} no longer sits on the same bases")
    return errs


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backbone", required=True)
    ap.add_argument("--product", required=True)
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--end", type=int, required=True)
    ap.add_argument("--insert", required=True, help="sequence, or @file")
    ap.add_argument("--feature", help="name of the feature annotating the insert")
    ap.add_argument("--oligo", action="append", default=[],
                    help="oligo that must occur exactly once; repeatable")
    ap.add_argument("--dropped", action="append", default=[],
                    help="backbone feature deliberately not carried over; repeatable")
    a = ap.parse_args()
    insert = "".join(open(a.insert[1:]).read().split()) if a.insert.startswith("@") else a.insert
    errs = check(a.backbone, a.product, a.start, a.end, insert,
                 feature=a.feature, oligos=a.oligo, dropped=a.dropped)
    name = a.product.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
    if errs:
        print("FAIL " + name)
        for e in errs:
            print("      " + e)
        sys.exit(1)
    print("ok   " + name)


if __name__ == "__main__":
    main()
